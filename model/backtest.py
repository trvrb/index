"""Rolling-origin backtest of citation forecasts.

For each origin year, truncates the data at that year, refits the model, and
scores predictions of each paper's citations in the following full years.

Usage:
    python -m model.backtest --input results/citations.json
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np
from scipy.special import gammaln, logsumexp
from scipy.stats import poisson

from .data import build_series, load_citations, parse_scraped_at, to_arrays
from .kalman import ModelParams, poisson_laplace
from .tune import DEFAULT_DRIFT_AGES, fit_hyperparameters

GH_NODES, GH_WEIGHTS = np.polynomial.hermite_e.hermegauss(60)
GH_LOG_WEIGHTS = np.log(GH_WEIGHTS / GH_WEIGHTS.sum())


@dataclass
class Predictive:
    """Lognormal-Poisson predictive distributions for a set of papers."""

    mean: np.ndarray  # mean of log rate
    var: np.ndarray  # variance of log rate
    truncated: np.ndarray  # zero-truncated observation

    def _rates(self) -> np.ndarray:
        x = self.mean[:, None] + np.sqrt(self.var)[:, None] * GH_NODES[None, :]
        return np.exp(np.minimum(x, 20))

    def log_pmf(self, y: np.ndarray) -> np.ndarray:
        mu = self._rates()
        log_p = y[:, None] * np.log(mu) - mu - gammaln(y[:, None] + 1)
        log_p = np.where(self.truncated[:, None], log_p - np.log(-np.expm1(-mu)), log_p)
        return logsumexp(log_p + GH_LOG_WEIGHTS[None, :], axis=1)

    def cdf(self, k: np.ndarray) -> np.ndarray:
        mu = self._rates()
        k = k[:, None]
        cdf = poisson.cdf(k, mu)
        p0 = np.exp(-mu)
        cdf = np.where(self.truncated[:, None], np.clip((cdf - p0) / (1 - p0), 0, 1), cdf)
        weights = np.exp(GH_LOG_WEIGHTS)[None, :]
        return (cdf * weights).sum(axis=1)

    def quantile(self, p: float) -> np.ndarray:
        """Smallest k with CDF(k) >= p, found by bisection."""
        lo = np.full(self.mean.shape, -1.0)
        hi = poisson.ppf(0.99999, self._rates().max(axis=1)) + 1
        while np.any(hi - lo > 1):
            mid = np.floor((lo + hi) / 2)
            above = self.cdf(mid) >= p
            hi = np.where(above, mid, hi)
            lo = np.where(above, lo, mid)
        return hi

    def expected(self) -> np.ndarray:
        mu = self._rates()
        mu = np.where(self.truncated[:, None], mu / -np.expm1(-mu), mu)
        return (mu * np.exp(GH_LOG_WEIGHTS)[None, :]).sum(axis=1)


def predict(
    papers: list[dict],
    scraped_at,
    origin: int,
    target: int,
    params: ModelParams,
    laplace,
    series: list,
) -> tuple[dict[str, np.ndarray], dict[str, Predictive]]:
    """Build predictive distributions for the target year.

    Papers that existed at the origin are predicted from their posterior.
    Papers starting after the origin are predicted from the population prior.
    """
    drift = params.drift_by_age(target - min(s.years[0] for s in series) + 2)
    horizon = target - origin

    # Existing papers
    lengths = np.array([len(s.years) for s in series])
    rows = np.arange(len(series))
    last = lengths - 1
    mean = laplace.x[rows, last] + sum(drift[last + h] for h in range(1, horizon + 1))
    var = laplace.P[rows, last] + horizon * params.process_var
    titles = {s.title for s in series}
    truth_existing = []
    for s in series:
        paper = next(p for p in papers if p["title"] == s.title)
        truth_existing.append((paper.get("citations_by_year") or {}).get(str(target), 0))

    # Papers that start after the origin
    new_mean, new_var, new_trunc, truth_new = [], [], [], []
    for paper in papers:
        if paper["title"] in titles:
            continue
        s = build_series(paper, scraped_at, end_year=target)
        if s is None or s.years[0] <= origin:
            continue
        age = target - s.years[0]
        new_mean.append(params.init_mean + drift[1 : age + 1].sum())
        new_var.append(params.init_var + age * params.process_var)
        new_trunc.append(s.first_obs_truncated and age == 0)
        truth_new.append(s.counts[-1])

    truths = {
        "existing": np.array(truth_existing, dtype=float),
        "new": np.array(truth_new, dtype=float),
    }
    predictives = {
        "existing": Predictive(mean, var, np.zeros(len(series), dtype=bool)),
        "new": Predictive(np.array(new_mean), np.array(new_var), np.array(new_trunc, dtype=bool)),
    }
    return truths, predictives


def score(y: np.ndarray, pred: Predictive) -> dict[str, float]:
    """Log score, 80% interval coverage, median error and total ratio."""
    if y.size == 0:
        return {"n": 0}
    lower = pred.quantile(0.1)
    upper = pred.quantile(0.9)
    median = pred.quantile(0.5)
    return {
        "n": int(y.size),
        "log_score": float(pred.log_pmf(y).sum()),
        "covered": float(((y >= lower) & (y <= upper)).sum()),
        "abs_error": float(np.abs(np.log1p(median) - np.log1p(y)).sum()),
        "predicted_total": float(pred.expected().sum()),
        "observed_total": float(y.sum()),
    }


def main() -> None:
    """Run rolling-origin backtest."""
    parser = argparse.ArgumentParser(description="Backtest citation forecasts")
    parser.add_argument(
        "--input",
        "-i",
        default="results/citations.json",
        help="Path to citations.json (default: results/citations.json)",
    )
    parser.add_argument(
        "--origins",
        type=int,
        nargs="+",
        default=[2020, 2021, 2022, 2023],
        help="Last year of data used for fitting (default: 2020 2021 2022 2023)",
    )
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2],
        help="Years ahead to predict (default: 1 2)",
    )
    parser.add_argument(
        "--drift-ages",
        type=int,
        nargs="+",
        default=[0, DEFAULT_DRIFT_AGES],
        help=f"Drift parameter counts K to compare (default: 0 {DEFAULT_DRIFT_AGES})",
    )
    args = parser.parse_args()

    data = load_citations(args.input)
    scraped_at = parse_scraped_at(data["scraped_at"])
    papers = [p for p in data.get("papers", []) if p.get("citations_by_year") is not None]

    print(f"{'K':>2} {'h':>2} {'group':>8} {'n':>5} {'log score':>10} "
          f"{'80% cov':>8} {'MAE log1p':>10} {'pred/obs total by origin'}")
    for K in args.drift_ages:
        totals: dict[tuple[int, str], dict] = {}
        for origin in args.origins:
            series = [s for p in papers if (s := build_series(p, scraped_at, end_year=origin))]
            Y, E, mask, trunc = to_arrays(series)
            params, _ = fit_hyperparameters(Y, E, mask, trunc, K)
            laplace = poisson_laplace(Y, E, mask, trunc, params)

            for h in args.horizons:
                target = origin + h
                if target >= scraped_at.year:
                    continue
                truths, predictives = predict(
                    papers, scraped_at, origin, target, params, laplace, series
                )
                for group in ("existing", "new"):
                    result = score(truths[group], predictives[group])
                    entry = totals.setdefault((h, group), {"ratios": []})
                    if result["n"] == 0:
                        continue
                    for key in ("n", "log_score", "covered", "abs_error"):
                        entry[key] = entry.get(key, 0) + result[key]
                    entry["ratios"].append(result["predicted_total"] / max(1, result["observed_total"]))

        for (h, group), entry in sorted(totals.items()):
            n = entry.get("n", 0)
            if not n:
                continue
            ratios = " ".join(f"{r:.2f}" for r in entry["ratios"])
            print(f"{K:>2} {h:>2} {group:>8} {n:>5} {entry['log_score'] / n:>10.3f} "
                  f"{entry['covered'] / n:>8.2f} {entry['abs_error'] / n:>10.3f} {ratios}")


if __name__ == "__main__":
    main()
