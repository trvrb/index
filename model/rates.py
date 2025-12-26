"""CLI for citation rate analysis using Kalman smoothing.

Usage:
    python -m model.rates --input results/citations.json --output results/citation_rates.json
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np

from .kalman import compute_obs_variance, kalman_smoother_1d


def parse_scraped_at(scraped_at_str: str) -> datetime:
    """Parse scraped_at timestamp to timezone-aware datetime."""
    # Handle ISO format with timezone
    if scraped_at_str.endswith("Z"):
        scraped_at_str = scraped_at_str[:-1] + "+00:00"
    return datetime.fromisoformat(scraped_at_str)


def compute_exposure_fraction(scraped_at: datetime) -> float:
    """Compute fraction of current year that has been observed.

    Returns:
        Fraction between 0 and 1 representing how much of the year has passed.
    """
    current_year = scraped_at.year
    tz = scraped_at.tzinfo or timezone.utc

    year_start = datetime(current_year, 1, 1, tzinfo=tz)
    next_year_start = datetime(current_year + 1, 1, 1, tzinfo=tz)

    total_seconds = (next_year_start - year_start).total_seconds()
    elapsed_seconds = (scraped_at - year_start).total_seconds()

    fraction = elapsed_seconds / total_seconds

    # Sanity check
    if not (0.0 < fraction <= 1.0):
        return 1.0

    return fraction


def analyze_paper(
    paper: dict[str, Any],
    scraped_at: datetime,
    process_var: float,
    min_count: float,
    obs_var: Optional[float] = None,
    obs_overdispersion: Optional[float] = None,
    forecast_years: int = 0,
) -> dict[str, Any]:
    """Analyze a single paper's citation time series.

    Args:
        paper: Paper dict with title and citations_by_year.
        scraped_at: When the data was scraped.
        process_var: Process variance for Kalman filter.
        min_count: Pseudocount to add before log transform.
        obs_var: Constant observation variance (if not using overdispersion).
        obs_overdispersion: Overdispersion factor φ for time-varying variance.
        forecast_years: Number of years to forecast into the future.

    Returns:
        Dict with years, observed counts, empirical rates, smoothed rates, and forecasts.
    """
    citations = paper.get("citations_by_year", {})

    # Handle empty citations
    if not citations:
        return {
            "title": paper["title"],
            "years": [],
            "observed_citations": [],
            "exposure_fraction": [],
            "empirical_rate": [],
            "smoothed_rate": [],
            "smoothed_log_rate": [],
            "smoothed_rate_std": [],
        }

    # Build year grid from available data
    years = sorted(int(y) for y in citations.keys())
    current_year = scraped_at.year

    # Get counts for each year (0 if missing within range)
    counts = np.array([citations.get(str(y), 0) for y in years], dtype=float)

    # Build exposure array
    exposure = np.ones_like(counts)
    if years[-1] == current_year:
        exposure[-1] = compute_exposure_fraction(scraped_at)

    # Empirical rates (annualized)
    empirical = counts / np.maximum(exposure, 1e-6)

    # Transform to log space with pseudocount
    z = np.log(empirical + min_count)

    # Determine observation variance
    if obs_overdispersion is not None:
        # Time-varying variance based on Poisson approximation
        R_t = compute_obs_variance(empirical, obs_overdispersion, min_count)
    else:
        # Constant variance
        R_t = obs_var if obs_var is not None else 0.3

    # Run Kalman smoother
    x_smooth, P_smooth = kalman_smoother_1d(
        z,
        process_var=process_var,
        obs_var=R_t,
        x0_mean=z[0],
        x0_var=1.0,
    )

    # Back-transform to rate space
    smoothed_rate = np.exp(x_smooth)
    smoothed_std = smoothed_rate * np.sqrt(P_smooth)

    result = {
        "title": paper["title"],
        "years": years,
        "observed_citations": counts.tolist(),
        "exposure_fraction": exposure.tolist(),
        "empirical_rate": empirical.tolist(),
        "smoothed_rate": smoothed_rate.tolist(),
        "smoothed_log_rate": x_smooth.tolist(),
        "smoothed_rate_std": smoothed_std.tolist(),
    }

    # Add forecasts if requested
    if forecast_years > 0:
        last_year = years[-1]
        forecast_years_list = [last_year + h for h in range(1, forecast_years + 1)]

        # Get final smoothed state
        x_T = x_smooth[-1]
        P_T = P_smooth[-1]

        # Compute forecasts for each horizon
        f_log_var = []
        f_rate_median = []
        f_rate_std = []
        f_sampled_log_rate = []
        f_sampled_rate = []

        # For observation noise sampling
        sigma_min = 0.1
        phi = obs_overdispersion if obs_overdispersion is not None else 0.56

        for h in range(1, forecast_years + 1):
            # Forecast variance grows linearly with horizon
            var_h = P_T + h * process_var
            mean_h = x_T  # Mean stays constant (random walk has no drift)

            f_log_var.append(float(var_h))

            # Transform to rate space (lognormal distribution)
            median_lambda = math.exp(mean_h)
            var_lambda = (math.exp(var_h) - 1.0) * math.exp(2 * mean_h + var_h)
            std_lambda = math.sqrt(var_lambda)

            f_rate_median.append(median_lambda)
            f_rate_std.append(std_lambda)

            # Sample state (log-rate) from forecast distribution
            log_rate_sample = np.random.normal(mean_h, math.sqrt(var_h))

            # Compute observation variance (same formula as compute_obs_variance)
            rate_sample = math.exp(log_rate_sample)
            R_h = phi / (rate_sample + min_count) + sigma_min**2

            # Sample observed log-rate with observation noise
            sampled_log_rate = np.random.normal(log_rate_sample, math.sqrt(R_h))
            sampled_rate = math.exp(sampled_log_rate)

            f_sampled_log_rate.append(float(sampled_log_rate))
            f_sampled_rate.append(float(sampled_rate))

        result.update({
            "forecast_years": forecast_years_list,
            "forecast_log_rate_var": f_log_var,
            "forecast_rate_median": f_rate_median,
            "forecast_rate_std": f_rate_std,
            "forecast_sampled_log_rate": f_sampled_log_rate,
            "forecast_sampled_rate": f_sampled_rate,
        })

    return result


def check_citation_totals(paper: dict[str, Any], analyzed: dict[str, Any]) -> None:
    """Warn if observed citations don't match total_citations."""
    total_from_years = sum(analyzed["observed_citations"])
    expected_total = paper.get("total_citations", 0)

    if abs(total_from_years - expected_total) > 0.5:
        print(
            f"  Warning: {paper['title'][:50]}... "
            f"sum={total_from_years}, total_citations={expected_total}"
        )


def main() -> None:
    """Run citation rate analysis."""
    parser = argparse.ArgumentParser(
        description="Analyze citation rates using Kalman smoothing"
    )
    parser.add_argument(
        "--input",
        "-i",
        required=True,
        help="Path to citations.json",
    )
    parser.add_argument(
        "--output",
        "-o",
        required=True,
        help="Path for output JSON",
    )
    parser.add_argument(
        "--model",
        choices=["kalman"],
        default="kalman",
        help="Smoothing model (default: kalman)",
    )
    parser.add_argument(
        "--process-var",
        type=float,
        default=0.25,
        help="Process variance on log-rate random walk (default: 0.25)",
    )
    parser.add_argument(
        "--obs-var",
        type=float,
        default=None,
        help="Constant observation noise variance on log counts",
    )
    parser.add_argument(
        "--obs-overdispersion",
        type=float,
        default=0.56,
        help="Overdispersion factor φ for time-varying observation variance (default: 0.56)",
    )
    parser.add_argument(
        "--min-count",
        type=float,
        default=0.5,
        help="Pseudocount added before log transform (default: 0.5)",
    )
    parser.add_argument(
        "--forecast-years",
        type=int,
        default=5,
        help="Number of years to forecast into the future (default: 5)",
    )

    args = parser.parse_args()

    # If obs-var is explicitly set, disable overdispersion
    if args.obs_var is not None:
        args.obs_overdispersion = None

    # Load input
    print(f"Loading {args.input}...")
    with open(args.input) as f:
        data = json.load(f)

    # Parse scraped_at
    scraped_at = parse_scraped_at(data["scraped_at"])
    print(f"Data scraped at: {scraped_at}")
    print(f"Exposure fraction for {scraped_at.year}: {compute_exposure_fraction(scraped_at):.3f}")

    # Analyze each paper
    papers = data.get("papers", [])
    print(f"Analyzing {len(papers)} papers...")
    if args.forecast_years > 0:
        print(f"Forecasting {args.forecast_years} years into the future...")

    analyzed_papers = []
    for paper in papers:
        analyzed = analyze_paper(
            paper,
            scraped_at,
            process_var=args.process_var,
            min_count=args.min_count,
            obs_var=args.obs_var,
            obs_overdispersion=args.obs_overdispersion,
            forecast_years=args.forecast_years,
        )
        check_citation_totals(paper, analyzed)
        analyzed_papers.append(analyzed)

    # Build model metadata
    model_info = {
        "type": args.model,
        "process_var": args.process_var,
        "min_count": args.min_count,
    }
    if args.obs_overdispersion is not None:
        model_info["obs_overdispersion"] = args.obs_overdispersion
    else:
        model_info["obs_var"] = args.obs_var

    # Build output
    result = {
        "user_id": data.get("user_id"),
        "scraped_at": data.get("scraped_at"),
        "model": model_info,
        "papers": analyzed_papers,
    }

    # Add forecast metadata if forecasting was requested
    if args.forecast_years > 0:
        result["forecast"] = {
            "horizon_years": args.forecast_years,
            "assumptions": {
                "model": "random_walk_log_rate",
                "process_var": args.process_var,
                "obs_overdispersion": args.obs_overdispersion,
                "min_count": args.min_count,
            }
        }

    # Write output
    print(f"Writing {args.output}...")
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
