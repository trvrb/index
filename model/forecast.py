"""Monte Carlo forecasts of citations and h-index.

Draws each paper's current log rate and slope deviation from their Laplace
posterior, completes the current partial year, then propagates the damped
trend with age-specific drift H years forward. Draws are joint across
papers, so aggregate quantities such as total citations and h-index get
proper intervals.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .data import Series, h_index, i10_index
from .kalman import LaplaceResult, ModelParams, propagate

QUANTILES = (0.1, 0.5, 0.9)
DEFAULT_LEAD = 1.5


def forecast_horizon(exposure: float, lead: float = DEFAULT_LEAD) -> int:
    """Number of years to forecast after the current year.

    Forecasts run through the last year-end within `lead` years of the
    scrape date. With a lead of 1.5, a scrape before July forecasts through
    the end of the current year, and from July on through the end of next
    year.

    Args:
        exposure: Fraction of the current year elapsed at the scrape.
        lead: Maximum time from the scrape to the end of the forecast, in years.
    """
    return max(0, math.floor(exposure + lead) - 1)


@dataclass
class Forecast:
    """Forecast draws for years [current_year, ..., current_year + horizon].

    The first year is the year-end projection for the partial current year.
    """

    years: list[int]
    log_rate_mean: np.ndarray  # (n_papers, n_years) mean of x on log scale
    log_rate_var: np.ndarray  # (n_papers, n_years) variance of x
    counts: np.ndarray  # (n_samples, n_papers, n_years) dated citations per year
    cumulative: np.ndarray  # (n_samples, n_papers, n_years) dated cumulative citations
    undated: np.ndarray  # (n_papers,) undated citations, added for h-index
    extra_totals: np.ndarray  # totals of papers outside the model, for h-index


def simulate(
    series: list[Series],
    laplace: LaplaceResult,
    params: ModelParams,
    current_year: int,
    horizon: int = 3,
    n_samples: int = 2000,
    seed: int = 0,
    extra_totals: list[int] | None = None,
) -> Forecast:
    """Simulate citation counts for the rest of the current year and beyond.

    Args:
        series: Modeled papers (all ending at current_year).
        laplace: Posterior from poisson_laplace for the same papers.
        params: Model hyperparameters.
        current_year: The (possibly partial) final year of every series.
        horizon: Number of years to forecast after the current year.
        n_samples: Number of Monte Carlo draws.
        seed: Random seed.
        extra_totals: Total citations of papers that aren't modeled (no dated
            citations), which still count toward the h-index.

    Returns:
        Forecast.
    """
    rng = np.random.default_rng(seed)
    n_papers = len(series)
    lengths = np.array([len(s.years) for s in series])
    last = lengths - 1
    rows = np.arange(n_papers)

    state_T = laplace.state[rows, last]  # (x, d) at the current year
    cov_T = laplace.state_cov[rows, last]
    y_T = np.array([s.counts[-1] for s in series])
    e_T = np.array([s.exposure[-1] for s in series])
    observed_before = np.array([s.counts[:-1].sum() for s in series])

    drift = params.drift_by_age(int(lengths.max()) + horizon + 1)
    years = [current_year + h for h in range(horizon + 1)]

    # Analytic log-rate distribution per year
    log_mean, log_var = propagate(state_T, cov_T, last, params, horizon)

    # Joint draws of (x, d); a small jitter keeps degenerate slopes factorable
    chol = np.linalg.cholesky(cov_T + 1e-10 * np.eye(2))
    state = state_T + np.einsum("nij,snj->sni", chol, rng.standard_normal((n_samples, n_papers, 2)))
    x, d = state[..., 0], state[..., 1]

    counts = np.zeros((n_samples, n_papers, horizon + 1))
    remaining = np.clip(1.0 - e_T, 0.0, 1.0)
    counts[:, :, 0] = y_T + rng.poisson(remaining * np.exp(np.minimum(x, 20)))
    rho = params.persistence
    for h in range(1, horizon + 1):
        zeta = np.sqrt(params.slope_var) * rng.standard_normal(x.shape)
        eps = np.sqrt(params.process_var) * rng.standard_normal(x.shape)
        x = x + drift[last + h] + rho * d + zeta + eps
        d = rho * d + zeta
        counts[:, :, h] = rng.poisson(np.exp(np.minimum(x, 20)))

    cumulative = observed_before[None, :, None] + np.cumsum(counts, axis=2)

    return Forecast(
        years=years,
        log_rate_mean=log_mean,
        log_rate_var=log_var,
        counts=counts,
        cumulative=cumulative,
        undated=np.array([s.undated_citations for s in series], dtype=float),
        extra_totals=np.array(extra_totals or [], dtype=float),
    )


def _quantiles(draws: np.ndarray, axis: int = 0) -> dict[str, np.ndarray]:
    q = np.quantile(draws, QUANTILES, axis=axis)
    return {f"q{int(round(p * 100))}": q[k] for k, p in enumerate(QUANTILES)}


def paper_summaries(forecast: Forecast) -> list[dict[str, list[float]]]:
    """Per-paper forecast summaries for each forecast year.

    Rate quantiles are analytic (lognormal); cumulative quantiles are from
    the Monte Carlo draws.
    """
    from scipy.stats import norm

    z = norm.ppf(QUANTILES)
    rate_mean = np.exp(forecast.log_rate_mean + forecast.log_rate_var / 2)
    rate_q = [np.exp(forecast.log_rate_mean + zq * np.sqrt(forecast.log_rate_var)) for zq in z]
    cumulative_q = _quantiles(forecast.cumulative, axis=0)

    out = []
    for i in range(forecast.log_rate_mean.shape[0]):
        out.append({
            "rate_mean": rate_mean[i].tolist(),
            "rate_q10": rate_q[0][i].tolist(),
            "rate_q50": rate_q[1][i].tolist(),
            "rate_q90": rate_q[2][i].tolist(),
            "cumulative_q10": cumulative_q["q10"][i].tolist(),
            "cumulative_q50": cumulative_q["q50"][i].tolist(),
            "cumulative_q90": cumulative_q["q90"][i].tolist(),
        })
    return out


def aggregate_summary(forecast: Forecast) -> dict[str, list[float]]:
    """Quantiles of total yearly citations, h-index and i10-index per year.

    The h-index and i10-index include undated citations and unmodeled papers
    so they are consistent with Scholar's profile numbers.
    """
    n_samples = forecast.counts.shape[0]
    totals = forecast.cumulative + forecast.undated[None, :, None]
    if forecast.extra_totals.size:
        extra = np.broadcast_to(
            forecast.extra_totals[None, :, None],
            (n_samples, forecast.extra_totals.size, totals.shape[2]),
        )
        totals = np.concatenate([totals, extra], axis=1)

    # Move papers to the last axis for the index functions
    totals = np.moveaxis(totals, 1, 2)
    h = h_index(totals)
    i10 = i10_index(totals)
    citations = forecast.counts.sum(axis=1)
    cumulative = totals.sum(axis=2)

    out: dict[str, list[float]] = {}
    for name, draws in [
        ("citations", citations),
        ("cumulative", cumulative),
        ("h_index", h),
        ("i10_index", i10),
    ]:
        for key, values in _quantiles(draws, axis=0).items():
            out[f"{name}_{key}"] = values.tolist()
    return out
