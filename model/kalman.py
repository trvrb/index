"""Poisson state-space model for citation rates.

Each paper's log citation rate follows a random walk whose mean step depends
on the paper's age (years since its start year):

    x_0 ~ N(m0, v0)
    x_a = x_{a-1} + delta_{min(a, K)} + eps_a,   eps_a ~ N(0, q)
    y_a ~ Poisson(e_a * exp(x_a))

where e_a is the fraction of the year observed. The first count is
zero-truncated when a series starts at its first cited year.

Inference uses the Laplace approximation: Newton iterations on the latent
path, each of which is a Kalman filter + RTS smoother pass on Gaussian
working observations. All functions operate on a batch of papers at once,
with arrays shaped (n_papers, n_ages) and a mask marking observed cells.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.special import gammaln

LOG_2PI = np.log(2 * np.pi)


@dataclass
class ModelParams:
    """Hyperparameters shared across papers."""

    process_var: float  # q: variance of yearly log-rate steps
    init_mean: float  # m0: mean log rate in a paper's first year
    init_var: float  # v0: variance of log rate in a paper's first year
    drift: list[float] = field(default_factory=list)  # delta_1..delta_K

    def drift_by_age(self, n_ages: int) -> np.ndarray:
        """Mean log-rate step into each age (entry 0 is unused)."""
        out = np.zeros(n_ages)
        if self.drift:
            for age in range(1, n_ages):
                out[age] = self.drift[min(age, len(self.drift)) - 1]
        return out

    def to_dict(self) -> dict:
        return {
            "process_var": self.process_var,
            "init_mean": self.init_mean,
            "init_var": self.init_var,
            "drift": list(self.drift),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelParams":
        return cls(
            process_var=float(d["process_var"]),
            init_mean=float(d["init_mean"]),
            init_var=float(d["init_var"]),
            drift=[float(v) for v in d.get("drift", [])],
        )


@dataclass
class LaplaceResult:
    """Posterior mode and approximate marginal likelihood."""

    x: np.ndarray  # posterior mode of log rate, (n_papers, n_ages)
    P: np.ndarray  # posterior variance of log rate, (n_papers, n_ages)
    loglik: np.ndarray  # Laplace log marginal likelihood per paper
    n_iter: int


def kalman_filter(
    z: np.ndarray,
    R: np.ndarray,
    mask: np.ndarray,
    params: ModelParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Run a batched Kalman filter on Gaussian observations z ~ N(x, R).

    Cells with mask False are skipped (prediction only).

    Returns:
        Tuple of (x_pred, P_pred, x_filt, P_filt, loglik) where loglik is the
        log-likelihood of each row.
    """
    n_papers, n_ages = z.shape
    drift = params.drift_by_age(n_ages)

    x_pred = np.zeros((n_papers, n_ages))
    P_pred = np.zeros((n_papers, n_ages))
    x_filt = np.zeros((n_papers, n_ages))
    P_filt = np.zeros((n_papers, n_ages))
    loglik = np.zeros(n_papers)

    for a in range(n_ages):
        if a == 0:
            x_pred[:, 0] = params.init_mean
            P_pred[:, 0] = params.init_var
        else:
            x_pred[:, a] = x_filt[:, a - 1] + drift[a]
            P_pred[:, a] = P_filt[:, a - 1] + params.process_var

        m = mask[:, a]
        S = P_pred[:, a] + np.where(m, R[:, a], 1.0)  # innovation variance
        v = np.where(m, z[:, a] - x_pred[:, a], 0.0)  # innovation
        K = np.where(m, P_pred[:, a] / S, 0.0)  # Kalman gain

        x_filt[:, a] = x_pred[:, a] + K * v
        P_filt[:, a] = (1 - K) * P_pred[:, a]
        loglik += np.where(m, -0.5 * (LOG_2PI + np.log(S) + v**2 / S), 0.0)

    return x_pred, P_pred, x_filt, P_filt, loglik


def rts_smoother(
    x_pred: np.ndarray,
    P_pred: np.ndarray,
    x_filt: np.ndarray,
    P_filt: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the Rauch-Tung-Striebel backward pass on Kalman filter output."""
    x_smooth = x_filt.copy()
    P_smooth = P_filt.copy()
    for a in range(x_filt.shape[1] - 2, -1, -1):
        C = P_filt[:, a] / P_pred[:, a + 1]
        x_smooth[:, a] = x_filt[:, a] + C * (x_smooth[:, a + 1] - x_pred[:, a + 1])
        P_smooth[:, a] = P_filt[:, a] + C**2 * (P_smooth[:, a + 1] - P_pred[:, a + 1])
    return x_smooth, P_smooth


def kalman_smoother(
    z: np.ndarray,
    R: np.ndarray,
    mask: np.ndarray,
    params: ModelParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run Kalman filter and RTS smoother.

    Returns:
        Tuple of (x_smooth, P_smooth, loglik per row).
    """
    x_pred, P_pred, x_filt, P_filt, loglik = kalman_filter(z, R, mask, params)
    x_smooth, P_smooth = rts_smoother(x_pred, P_pred, x_filt, P_filt)
    return x_smooth, P_smooth, loglik


def poisson_terms(
    Y: np.ndarray,
    mu: np.ndarray,
    trunc: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Log-likelihood, score and observed information with respect to log(mu).

    Cells with trunc True use the zero-truncated Poisson.
    """
    loglik = Y * np.log(mu) - mu - gammaln(Y + 1)
    score = Y - mu
    info = mu.copy()

    if trunc.any():
        # p(y | y >= 1) = Poisson(y) / (1 - exp(-mu))
        one_minus = -np.expm1(-mu)
        g = mu / one_minus  # E[y | y >= 1]
        # d g / d mu, using its series expansion where mu is tiny
        g_prime = np.where(
            mu > 1e-4,
            (one_minus - mu * np.exp(-mu)) / one_minus**2,
            0.5 + mu / 6,
        )
        loglik = np.where(trunc, loglik - np.log(one_minus), loglik)
        score = np.where(trunc, Y - g, score)
        info = np.where(trunc, mu * g_prime, info)

    return loglik, score, info


def log_posterior(
    x: np.ndarray,
    Y: np.ndarray,
    E: np.ndarray,
    mask: np.ndarray,
    trunc: np.ndarray,
    params: ModelParams,
) -> np.ndarray:
    """Unnormalized log posterior of each row's latent path."""
    n_ages = x.shape[1]
    drift = params.drift_by_age(n_ages)

    obs, _, _ = poisson_terms(Y, E * np.exp(x), trunc)
    total = np.where(mask, obs, 0.0).sum(axis=1)

    total += -0.5 * (
        np.log(2 * np.pi * params.init_var)
        + (x[:, 0] - params.init_mean) ** 2 / params.init_var
    )
    steps = x[:, 1:] - x[:, :-1] - drift[1:]
    step_terms = -0.5 * (np.log(2 * np.pi * params.process_var) + steps**2 / params.process_var)
    total += np.where(mask[:, 1:], step_terms, 0.0).sum(axis=1)
    return total


def poisson_laplace(
    Y: np.ndarray,
    E: np.ndarray,
    mask: np.ndarray,
    trunc: np.ndarray,
    params: ModelParams,
    tol: float = 1e-8,
    max_iter: int = 100,
) -> LaplaceResult:
    """Find the posterior mode of each log-rate path and its Laplace likelihood.

    Each Newton step replaces the Poisson observations by Gaussian working
    observations z = x + score / info with variance 1 / info, around the
    current path, and runs the Kalman smoother. At convergence the
    smoother's variances are the Laplace posterior variances, and

        log p(y) ~= log L_KF(z) + sum[log p(y | x) - log N(z | x, 1 / info)]

    Args:
        Y: Counts, (n_papers, n_ages).
        E: Exposure fractions.
        mask: Observed cells.
        trunc: Cells with zero-truncated observations.
        params: Model hyperparameters.
        tol: Convergence tolerance on the largest change in log rate.
        max_iter: Maximum number of Newton iterations.

    Returns:
        LaplaceResult with mode, variances and per-paper log-likelihood.
    """
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        x = np.where(mask, np.log((Y + 0.5) / E), 0.0)
        objective = log_posterior(x, Y, E, mask, trunc, params)

        n_iter = 0
        for n_iter in range(1, max_iter + 1):
            _, score, info = poisson_terms(Y, E * np.exp(x), trunc)
            info = np.maximum(info, 1e-12)
            x_new, _, _ = kalman_smoother(x + score / info, 1.0 / info, mask, params)
            x_new = np.where(mask, x_new, 0.0)

            # Step-halving safeguard (rarely needed; the posterior is log-concave)
            step = x_new - x
            new_objective = log_posterior(x_new, Y, E, mask, trunc, params)
            worse = ~(new_objective >= objective - 1e-10 * np.abs(objective))
            for _ in range(30):
                if not worse.any():
                    break
                step[worse] *= 0.5
                x_new = x + step
                new_objective = log_posterior(x_new, Y, E, mask, trunc, params)
                worse = worse & ~(new_objective >= objective - 1e-10 * np.abs(objective))

            change = np.max(np.abs(step[mask])) if mask.any() else 0.0
            x, objective = x_new, new_objective
            if change < tol:
                break

        # Gaussian approximation at the mode
        mu = E * np.exp(x)
        obs, score, info = poisson_terms(Y, mu, trunc)
        info = np.maximum(info, 1e-12)
        R = 1.0 / info
        z = x + score / info
        _, P, gaussian_loglik = kalman_smoother(z, R, mask, params)

        gaussian_obs = -0.5 * (LOG_2PI + np.log(R) + (z - x) ** 2 / R)
        correction = np.where(mask, obs - gaussian_obs, 0.0).sum(axis=1)

    return LaplaceResult(x=x, P=P, loglik=gaussian_loglik + correction, n_iter=n_iter)
