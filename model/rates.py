"""CLI for citation rate analysis using a Poisson state-space model.

Usage:
    python -m model.rates --input results/citations.json --output data/citation_rates.json
"""

from __future__ import annotations

import argparse
import json
import math
from typing import Any

import numpy as np

from .data import (
    Series,
    build_series,
    compute_exposure_fraction,
    h_index,
    i10_index,
    load_citations,
    parse_scraped_at,
    to_arrays,
)
from .forecast import aggregate_summary, paper_summaries, simulate
from .kalman import ModelParams, poisson_laplace
from .tune import DEFAULT_DRIFT_AGES, fit_hyperparameters

INTERVAL = 0.8
Z_INTERVAL = 1.2815515655446004  # standard normal quantile at 0.9


def _round(value: Any, digits: int = 3) -> Any:
    """Round floats in nested lists/dicts to keep the output JSON compact."""
    if isinstance(value, float):
        return round(value, digits) if math.isfinite(value) else None
    if isinstance(value, (np.floating, np.integer)):
        return _round(value.item(), digits)
    if isinstance(value, dict):
        return {k: _round(v, digits) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_round(v, digits) for v in value]
    return value


def summarize_history(
    papers: list[dict[str, Any]],
    series_by_index: dict[int, Series],
    current_year: int,
) -> dict[str, Any]:
    """Compute observed h-index, i10-index and totals by year.

    Historical values use dated citations only. The "to date" values use
    Scholar's total citations (including undated ones) so they match the
    profile page.
    """
    modeled = list(series_by_index.values())
    first_year = min(s.years[0] for s in modeled)
    years = list(range(first_year, current_year + 1))

    # Cumulative dated citations per paper per year
    cumulative = np.zeros((len(modeled), len(years)))
    for i, s in enumerate(modeled):
        offset = s.years[0] - first_year
        cumulative[i, offset:] = np.cumsum(s.counts)
    yearly = np.diff(cumulative.sum(axis=0), prepend=0.0)

    totals_to_date = np.array([
        max(
            paper.get("total_citations") or 0,
            series_by_index[i].dated_citations if i in series_by_index else 0,
        )
        for i, paper in enumerate(papers)
    ])

    return {
        "years": years,
        "h_index": h_index(cumulative.T).tolist(),
        "i10_index": i10_index(cumulative.T).tolist(),
        "citations": yearly.tolist(),
        "cumulative": cumulative.sum(axis=0).tolist(),
        "citations_to_date": int(totals_to_date.sum()),
        "h_index_to_date": int(h_index(totals_to_date)),
        "i10_index_to_date": int(i10_index(totals_to_date)),
    }


def main() -> None:
    """Run citation rate analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze citation rates using a Poisson state-space model"
    )
    parser.add_argument(
        "--input",
        "-i",
        default="results/citations.json",
        help="Path to citations.json (default: results/citations.json)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="data/citation_rates.json",
        help="Path for output JSON (default: data/citation_rates.json)",
    )
    parser.add_argument(
        "--params",
        default=None,
        help="JSON from model.tune with fixed hyperparameters (default: fit to the data)",
    )
    parser.add_argument(
        "--drift-ages",
        type=int,
        default=DEFAULT_DRIFT_AGES,
        help=f"Number of age-specific drift parameters when fitting (default: {DEFAULT_DRIFT_AGES})",
    )
    parser.add_argument(
        "--forecast-years",
        type=int,
        default=3,
        help="Number of years to forecast after the current year (default: 3)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=2000,
        help="Number of Monte Carlo draws for forecasts (default: 2000)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Random seed for forecasts (default: 0)",
    )
    args = parser.parse_args()

    print(f"Loading {args.input}...")
    data = load_citations(args.input)
    scraped_at = parse_scraped_at(data["scraped_at"])
    current_year = scraped_at.year
    exposure = compute_exposure_fraction(scraped_at)
    print(f"Data scraped at: {scraped_at} ({exposure:.1%} of {current_year} observed)")

    papers = data.get("papers", [])
    n_unscraped = sum(1 for p in papers if p.get("citations_by_year") is None)
    if n_unscraped:
        print(f"  Warning: {n_unscraped} papers haven't been scraped yet (resume with "
              f"`python -m ingest`); they're left out of rates and h-index")
    stale = [p for p in papers if p.get("stale") and p.get("citations_by_year") is not None]
    if stale:
        oldest = min(p.get("scraped_at") or data["scraped_at"] for p in stale)
        print(f"  Warning: {len(stale)} papers have newer counts on Scholar than stored "
              f"(oldest from {oldest[:10]}); run `python -m ingest` to update")
    series_by_index = {}
    unmodeled_totals = []
    for i, paper in enumerate(papers):
        s = build_series(paper, scraped_at)
        if s is None:
            unmodeled_totals.append(paper.get("total_citations") or 0)
        else:
            series_by_index[i] = s
    indices = list(series_by_index)
    series = [series_by_index[i] for i in indices]
    print(f"Modeling {len(series)} of {len(papers)} papers "
          f"({len(papers) - len(series) - n_unscraped} have no dated citations or publication year)")

    Y, E, mask, trunc = to_arrays(series)
    n_zero = int((Y[mask] == 0).sum())
    print(f"  {int(mask.sum())} paper-years, including {n_zero} zero years")

    undated = sum(s.undated_citations for s in series)
    if undated:
        print(f"  {undated} citations ({undated / max(1, undated + Y.sum()):.1%}) "
              f"have no year on Scholar; they count toward h-index but not rates")

    if args.params:
        with open(args.params) as f:
            tuned = json.load(f)
        params = ModelParams.from_dict(tuned.get("params", tuned))
        print(f"Using hyperparameters from {args.params}")
    else:
        print(f"Fitting hyperparameters (K={args.drift_ages})...")
        params, _ = fit_hyperparameters(Y, E, mask, trunc, args.drift_ages)
    print(f"  q={params.process_var:.4f} m0={params.init_mean:.4f} "
          f"v0={params.init_var:.4f} drift={[round(d, 4) for d in params.drift]}")

    laplace = poisson_laplace(Y, E, mask, trunc, params)
    loglik = float(laplace.loglik.sum())
    print(f"  log-likelihood: {loglik:.2f} ({laplace.n_iter} Newton iterations)")

    print(f"Forecasting {args.forecast_years} years with {args.samples} draws...")
    forecast = simulate(
        series,
        laplace,
        params,
        current_year,
        horizon=args.forecast_years,
        n_samples=args.samples,
        seed=args.seed,
        extra_totals=unmodeled_totals,
    )
    paper_forecasts = paper_summaries(forecast)
    aggregate = aggregate_summary(forecast)

    analyzed = []
    for row, (index, s) in enumerate(zip(indices, series)):
        n = len(s.years)
        x = laplace.x[row, :n]
        sd = np.sqrt(laplace.P[row, :n])
        analyzed.append({
            "title": s.title,
            "pub_year": s.pub_year,
            "total_citations": s.total_citations,
            "years": s.years,
            "observed_citations": s.counts.astype(int).tolist(),
            "exposure_fraction": s.exposure.tolist(),
            "empirical_rate": (s.counts / s.exposure).tolist(),
            "smoothed_rate": np.exp(x).tolist(),
            "smoothed_rate_mean": np.exp(x + sd**2 / 2).tolist(),
            "smoothed_rate_lower": np.exp(x - Z_INTERVAL * sd).tolist(),
            "smoothed_rate_upper": np.exp(x + Z_INTERVAL * sd).tolist(),
            "forecast": paper_forecasts[row],
        })

    summary = summarize_history(papers, series_by_index, current_year)
    print(f"h-index: {summary['h_index_to_date']} to date; "
          f"{current_year} year-end projection {aggregate['h_index_q50'][0]:.0f} "
          f"(80%: {aggregate['h_index_q10'][0]:.0f}-{aggregate['h_index_q90'][0]:.0f})")
    profile = data.get("profile") or {}
    for key in ("h_index", "i10_index"):
        if profile.get(key) is not None and profile[key] != summary[f"{key}_to_date"]:
            print(f"  Note: Scholar profile reports {key} {profile[key]}, "
                  f"computed {summary[f'{key}_to_date']} from per-paper counts")

    result = {
        "user_id": data.get("user_id"),
        "scraped_at": data.get("scraped_at"),
        "current_year": current_year,
        "exposure_fraction_current": exposure,
        "model": {
            "type": "poisson_state_space",
            **params.to_dict(),
            "drift_ages": len(params.drift),
            "log_likelihood": loglik,
            "interval": INTERVAL,
        },
        "profile": data.get("profile"),
        "summary": summary,
        "forecast": {"years": forecast.years, **aggregate},
        "papers": analyzed,
    }

    print(f"Writing {args.output}...")
    with open(args.output, "w") as f:
        json.dump(_round(result), f, indent=1)
    print("Done!")


if __name__ == "__main__":
    main()
