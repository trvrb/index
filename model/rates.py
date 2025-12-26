"""CLI for citation rate analysis using Kalman smoothing.

Usage:
    python -m model.rates --input results/citations.json --output results/citation_rates.json
"""

from __future__ import annotations

import argparse
import json
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
) -> dict[str, Any]:
    """Analyze a single paper's citation time series.

    Args:
        paper: Paper dict with title and citations_by_year.
        scraped_at: When the data was scraped.
        process_var: Process variance for Kalman filter.
        min_count: Pseudocount to add before log transform.
        obs_var: Constant observation variance (if not using overdispersion).
        obs_overdispersion: Overdispersion factor φ for time-varying variance.

    Returns:
        Dict with years, observed counts, empirical rates, and smoothed rates.
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

    return {
        "title": paper["title"],
        "years": years,
        "observed_citations": counts.tolist(),
        "exposure_fraction": exposure.tolist(),
        "empirical_rate": empirical.tolist(),
        "smoothed_rate": smoothed_rate.tolist(),
        "smoothed_log_rate": x_smooth.tolist(),
        "smoothed_rate_std": smoothed_std.tolist(),
    }


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

    analyzed_papers = []
    for paper in papers:
        analyzed = analyze_paper(
            paper,
            scraped_at,
            process_var=args.process_var,
            min_count=args.min_count,
            obs_var=args.obs_var,
            obs_overdispersion=args.obs_overdispersion,
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

    # Write output
    print(f"Writing {args.output}...")
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
