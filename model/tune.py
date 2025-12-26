"""Hyperparameter tuning for Kalman filter via marginal likelihood.

Performs grid search over process variance (q) and overdispersion (φ)
to find optimal parameters for the citation rate model.

Usage:
    python -m model.tune --input results/citations.json --output results/tuned_hyperparams.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any

import numpy as np

from .kalman import compute_obs_variance, kalman_filter_1d


def parse_scraped_at(scraped_at_str: str) -> datetime:
    """Parse scraped_at timestamp to timezone-aware datetime."""
    if scraped_at_str.endswith("Z"):
        scraped_at_str = scraped_at_str[:-1] + "+00:00"
    return datetime.fromisoformat(scraped_at_str)


def compute_exposure_fraction(scraped_at: datetime) -> float:
    """Compute fraction of current year observed."""
    current_year = scraped_at.year
    tz = scraped_at.tzinfo or timezone.utc

    year_start = datetime(current_year, 1, 1, tzinfo=tz)
    next_year_start = datetime(current_year + 1, 1, 1, tzinfo=tz)

    total_seconds = (next_year_start - year_start).total_seconds()
    elapsed_seconds = (scraped_at - year_start).total_seconds()

    fraction = elapsed_seconds / total_seconds
    if not (0.0 < fraction <= 1.0):
        return 1.0
    return fraction


def prepare_paper_data(
    paper: dict[str, Any],
    scraped_at: datetime,
    min_count: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Prepare observation and empirical rate arrays for a paper.

    Returns:
        Tuple of (z, empirical_rate) or None if paper has no citations.
    """
    citations = paper.get("citations_by_year", {})
    if not citations:
        return None

    years = sorted(int(y) for y in citations.keys())
    current_year = scraped_at.year

    counts = np.array([citations.get(str(y), 0) for y in years], dtype=float)

    exposure = np.ones_like(counts)
    if years[-1] == current_year:
        exposure[-1] = compute_exposure_fraction(scraped_at)

    # Empirical rates (annualized)
    empirical = counts / np.maximum(exposure, 1e-6)

    # Transform to log space
    z = np.log(empirical + min_count)

    return z, empirical


def compute_total_log_likelihood(
    papers_data: list[tuple[np.ndarray, np.ndarray]],
    process_var: float,
    overdispersion: float,
    min_count: float,
    sigma_min_sq: float = 0.01,
) -> float:
    """Compute total log-likelihood across all papers for given hyperparameters.

    Args:
        papers_data: List of (z, empirical_rate) tuples for each paper.
        process_var: Process variance q.
        overdispersion: Overdispersion factor φ.
        min_count: Pseudocount for log transform.
        sigma_min_sq: Floor variance.

    Returns:
        Sum of log-likelihoods across all papers.
    """
    total_log_lik = 0.0

    for z, empirical in papers_data:
        if len(z) < 2:
            # Skip papers with fewer than 2 years
            continue

        # Compute time-varying observation variance
        R_t = compute_obs_variance(empirical, overdispersion, min_count, sigma_min_sq)

        # Run Kalman filter to get log-likelihood
        _, _, _, _, log_lik = kalman_filter_1d(
            z,
            process_var=process_var,
            obs_var=R_t,
            x0_mean=z[0],
            x0_var=1.0,
        )

        total_log_lik += log_lik

    return total_log_lik


def grid_search(
    papers_data: list[tuple[np.ndarray, np.ndarray]],
    min_count: float,
    n_grid: int = 40,
) -> tuple[float, float, float, np.ndarray]:
    """Perform grid search over process_var and overdispersion.

    Args:
        papers_data: List of (z, empirical_rate) tuples.
        min_count: Pseudocount for log transform.
        n_grid: Number of grid points per dimension.

    Returns:
        Tuple of (best_q, best_phi, best_log_lik, log_lik_grid).
    """
    # Grid ranges from design doc
    # q in exp(linspace(-3, 1, n)) ≈ 0.05 to 2.7
    # φ in exp(linspace(-1, 2, n)) ≈ 0.37 to 7.4
    q_grid = np.exp(np.linspace(-3, 1, n_grid))
    phi_grid = np.exp(np.linspace(-1, 2, n_grid))

    log_lik_grid = np.zeros((n_grid, n_grid))

    best_log_lik = -np.inf
    best_q = q_grid[0]
    best_phi = phi_grid[0]

    print(f"Running grid search over {n_grid}x{n_grid} = {n_grid**2} parameter combinations...")

    for i, q in enumerate(q_grid):
        for j, phi in enumerate(phi_grid):
            log_lik = compute_total_log_likelihood(
                papers_data, q, phi, min_count
            )
            log_lik_grid[i, j] = log_lik

            if log_lik > best_log_lik:
                best_log_lik = log_lik
                best_q = q
                best_phi = phi

        # Progress indicator
        if (i + 1) % 10 == 0:
            print(f"  Completed {i + 1}/{n_grid} rows...")

    return best_q, best_phi, best_log_lik, log_lik_grid


def main() -> None:
    """Run hyperparameter tuning."""
    parser = argparse.ArgumentParser(
        description="Tune Kalman filter hyperparameters via marginal likelihood"
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
        help="Path for output JSON with tuned hyperparameters",
    )
    parser.add_argument(
        "--min-count",
        type=float,
        default=0.5,
        help="Pseudocount added before log transform (default: 0.5)",
    )
    parser.add_argument(
        "--n-grid",
        type=int,
        default=40,
        help="Number of grid points per dimension (default: 40)",
    )

    args = parser.parse_args()

    # Load input
    print(f"Loading {args.input}...")
    with open(args.input) as f:
        data = json.load(f)

    # Parse scraped_at
    scraped_at = parse_scraped_at(data["scraped_at"])
    print(f"Data scraped at: {scraped_at}")

    # Prepare data for all papers
    papers = data.get("papers", [])
    print(f"Preparing data for {len(papers)} papers...")

    papers_data = []
    for paper in papers:
        result = prepare_paper_data(paper, scraped_at, args.min_count)
        if result is not None:
            papers_data.append(result)

    print(f"  {len(papers_data)} papers have citation data")

    # Count papers with sufficient data
    n_valid = sum(1 for z, _ in papers_data if len(z) >= 2)
    print(f"  {n_valid} papers have >= 2 years of data")

    # Run grid search
    best_q, best_phi, best_log_lik, _ = grid_search(
        papers_data, args.min_count, args.n_grid
    )

    print(f"\nOptimal hyperparameters:")
    print(f"  process_var (q): {best_q:.4f}")
    print(f"  overdispersion (φ): {best_phi:.4f}")
    print(f"  log-likelihood: {best_log_lik:.2f}")

    # Build output
    result = {
        "input_file": args.input,
        "n_papers": len(papers_data),
        "n_papers_with_2plus_years": n_valid,
        "min_count": args.min_count,
        "n_grid": args.n_grid,
        "optimal": {
            "process_var": best_q,
            "overdispersion": best_phi,
            "log_likelihood": best_log_lik,
        },
    }

    # Write output
    print(f"\nWriting {args.output}...")
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print("Done!")


if __name__ == "__main__":
    main()
