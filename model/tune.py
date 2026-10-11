"""Hyperparameter fitting for the citation rate model via marginal likelihood.

Fits the process variance q, the first-year prior (m0, v0) and the
age-specific drift delta_1..delta_K by maximizing the Laplace-approximate
marginal likelihood summed across all papers.

Usage:
    python -m model.tune --input results/citations.json --output results/tuned_params.json
"""

from __future__ import annotations

import argparse
import json
import time
from typing import Optional

import numpy as np
from scipy.optimize import minimize

from .data import build_series, load_citations, parse_scraped_at, to_arrays
from .kalman import ModelParams, poisson_laplace

DEFAULT_DRIFT_AGES = 3


def _unpack(theta: np.ndarray) -> ModelParams:
    return ModelParams(
        process_var=float(np.exp(theta[0])),
        init_mean=float(theta[1]),
        init_var=float(np.exp(theta[2])),
        drift=[float(v) for v in theta[3:]],
    )


def fit_hyperparameters(
    Y: np.ndarray,
    E: np.ndarray,
    mask: np.ndarray,
    trunc: np.ndarray,
    drift_ages: int = DEFAULT_DRIFT_AGES,
    init: Optional[ModelParams] = None,
) -> tuple[ModelParams, float]:
    """Maximize the Laplace marginal likelihood over hyperparameters.

    Args:
        Y, E, mask, trunc: Arrays from data.to_arrays.
        drift_ages: Number of age-specific drift parameters K (0 gives a
            driftless random walk).
        init: Starting values.

    Returns:
        Tuple of (fitted params, total log-likelihood).
    """
    if init is None:
        default_drift = [0.5, 0.0, -0.05]
        init = ModelParams(
            process_var=0.2,
            init_mean=1.0,
            init_var=1.0,
            drift=[default_drift[min(k, 2)] for k in range(drift_ages)],
        )
    theta0 = np.array(
        [np.log(init.process_var), init.init_mean, np.log(init.init_var)]
        + list(init.drift[:drift_ages])
        + [0.0] * max(0, drift_ages - len(init.drift))
    )

    def neg_loglik(theta: np.ndarray) -> float:
        if np.any(np.abs(theta) > 20):
            return np.inf
        result = poisson_laplace(Y, E, mask, trunc, _unpack(theta))
        total = result.loglik.sum()
        return -total if np.isfinite(total) else np.inf

    options = {"maxiter": 2000 * len(theta0), "xatol": 1e-4, "fatol": 1e-4, "adaptive": True}
    result = minimize(neg_loglik, theta0, method="Nelder-Mead", options=options)
    # Restart from the optimum, since Nelder-Mead can stall
    result = minimize(neg_loglik, result.x, method="Nelder-Mead", options=options)

    return _unpack(result.x), -float(result.fun)


def main() -> None:
    """Fit hyperparameters and write them to JSON."""
    parser = argparse.ArgumentParser(
        description="Fit citation model hyperparameters via marginal likelihood"
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
        default="results/tuned_params.json",
        help="Path for output JSON (default: results/tuned_params.json)",
    )
    parser.add_argument(
        "--drift-ages",
        type=int,
        default=DEFAULT_DRIFT_AGES,
        help=f"Number of age-specific drift parameters (default: {DEFAULT_DRIFT_AGES})",
    )
    args = parser.parse_args()

    data = load_citations(args.input)
    scraped_at = parse_scraped_at(data["scraped_at"])
    series = [s for p in data.get("papers", []) if (s := build_series(p, scraped_at))]
    Y, E, mask, trunc = to_arrays(series)
    print(f"Fitting {len(series)} papers, {int(mask.sum())} paper-years "
          f"({int((Y[mask] == 0).sum())} zero years)...")

    start = time.time()
    params, loglik = fit_hyperparameters(Y, E, mask, trunc, args.drift_ages)
    print(f"Done in {time.time() - start:.1f}s")
    print(f"  process_var (q): {params.process_var:.4f}")
    print(f"  init_mean (m0):  {params.init_mean:.4f}")
    print(f"  init_var (v0):   {params.init_var:.4f}")
    print(f"  drift (delta):   {[round(d, 4) for d in params.drift]}")
    print(f"  log-likelihood:  {loglik:.2f}")

    result = {
        "input_file": args.input,
        "n_papers": len(series),
        "drift_ages": args.drift_ages,
        "params": params.to_dict(),
        "log_likelihood": loglik,
    }
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
