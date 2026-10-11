"""Poisson state-space model for citation rates.

Each paper's log citation rate x follows a damped local linear trend around
a population trajectory that depends on the paper's age (years since its
start year). The slope deviation d carries momentum: a paper growing faster
than typical keeps doing so, with the deviation decaying by rho each year.

    x_0 ~ N(m0, v0),  d_0 ~ N(0, r / (1 - rho^2))
    d_a = rho * d_{a-1} + zeta_a,                            zeta_a ~ N(0, r)
    x_a = x_{a-1} + delta_{min(a, K)} + rho * d_{a-1} + zeta_a + eps_a,   eps_a ~ N(0, q)
    y_a ~ Poisson(e_a * exp(x_a))

where e_a is the fraction of the year observed. With rho = 0 and r = 0 this
is a random walk with age-specific drift. The first count is zero-truncated
when a series starts at its first cited year.

Inference uses the Laplace approximation: Newton iterations on the latent
log-rate path, each of which is a Kalman filter + RTS smoother pass on
Gaussian working observations. All functions operate on a batch of papers at
once, with arrays shaped (n_papers, n_ages) and a mask marking observed cells.
State arrays have a trailing axis of size 2 for (x, d).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.special import gammaln

LOG_2PI = np.log(2 * np.pi)


@dataclass
class ModelParams:
    """Hyperparameters shared across papers."""

    process_var: float  # q: variance of yearly log-rate level shocks
    init_mean: float  # m0: mean log rate in a paper's first year
    init_var: float  # v0: variance of log rate in a paper's first year
    drift: list[float] = field(default_factory=list)  # delta_1..delta_K
    slope_var: float = 0.0  # r: variance of yearly slope shocks
    persistence: float = 0.0  # rho: fraction of a slope deviation kept each year

    def drift_by_age(self, n_ages: int) -> np.ndarray:
        """Mean log-rate step into each age (entry 0 is unused)."""
        out = np.zeros(n_ages)
        if self.drift:
            for age in range(1, n_ages):
                out[age] = self.drift[min(age, len(self.drift)) - 1]
        return out

    def transition(self) -> np.ndarray:
        """State transition matrix for (x, d)."""
        rho = self.persistence
        return np.array([[1.0, rho], [0.0, rho]])

    def noise_cov(self) -> np.ndarray:
        """Covariance of the yearly state shocks (eps + zeta, zeta)."""
        q, r = self.process_var, self.slope_var
        return np.array([[q + r, r], [r, r]])

    def init_cov(self) -> np.ndarray:
        """Covariance of (x_0, d_0); d_0 starts at its stationary variance."""
        slope_var = self.slope_var / max(1.0 - self.persistence**2, 1e-6)
        return np.diag([self.init_var, slope_var])

    def to_dict(self) -> dict:
        return {
            "process_var": self.process_var,
            "init_mean": self.init_mean,
            "init_var": self.init_var,
            "drift": list(self.drift),
            "slope_var": self.slope_var,
            "persistence": self.persistence,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ModelParams":
        return cls(
            process_var=float(d["process_var"]),
            init_mean=float(d["init_mean"]),
            init_var=float(d["init_var"]),
            drift=[float(v) for v in d.get("drift", [])],
            slope_var=float(d.get("slope_var", 0.0)),
            persistence=float(d.get("persistence", 0.0)),
        )


@dataclass
class LaplaceResult:
    """Posterior mode and approximate marginal likelihood."""

    x: np.ndarray  # posterior mode of log rate, (n_papers, n_ages)
    P: np.ndarray  # posterior variance of log rate, (n_papers, n_ages)
    state: np.ndarray  # posterior mean of (x, d), (n_papers, n_ages, 2)
    state_cov: np.ndarray  # posterior covariance of (x, d), (n_papers, n_ages, 2, 2)
    loglik: np.ndarray  # Laplace log marginal likelihood per paper
    n_iter: int


def kalman_filter(
    z: np.ndarray,
    R: np.ndarray,
    mask: np.ndarray,
    params: ModelParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Run a batched Kalman filter on Gaussian observations z ~ N(x, R).

    Cells with mask False are skipped (prediction only). R may be zero, in
    which case loglik is the prior log density of the path z.

    Returns:
        Tuple of (x_pred, P_pred, x_filt, P_filt, loglik), with states shaped
        (n_papers, n_ages, 2), covariances (n_papers, n_ages, 2, 2), and
        loglik the log-likelihood of each row.
    """
    n_papers, n_ages = z.shape
    drift = params.drift_by_age(n_ages)
    F = params.transition()
    Q = params.noise_cov()

    x_pred = np.zeros((n_papers, n_ages, 2))
    P_pred = np.zeros((n_papers, n_ages, 2, 2))
    x_filt = np.zeros((n_papers, n_ages, 2))
    P_filt = np.zeros((n_papers, n_ages, 2, 2))
    loglik = np.zeros(n_papers)

    for a in range(n_ages):
        if a == 0:
            x_pred[:, 0] = [params.init_mean, 0.0]
            P_pred[:, 0] = params.init_cov()
        else:
            x_pred[:, a] = x_filt[:, a - 1] @ F.T
            x_pred[:, a, 0] += drift[a]
            P_pred[:, a] = F @ P_filt[:, a - 1] @ F.T + Q

        m = mask[:, a]
        S = P_pred[:, a, 0, 0] + np.where(m, R[:, a], 1.0)  # innovation variance
        v = np.where(m, z[:, a] - x_pred[:, a, 0], 0.0)  # innovation
        K = np.where(m[:, None], P_pred[:, a, :, 0] / S[:, None], 0.0)  # Kalman gain

        x_filt[:, a] = x_pred[:, a] + K * v[:, None]
        P_filt[:, a] = P_pred[:, a] - K[:, :, None] * P_pred[:, a, None, 0, :]
        loglik += np.where(m, -0.5 * (LOG_2PI + np.log(S) + v**2 / S), 0.0)

    return x_pred, P_pred, x_filt, P_filt, loglik


def _inv2(M: np.ndarray) -> np.ndarray:
    """Invert a batch of 2x2 covariance matrices.

    Falls back to inverting the diagonal when a matrix is singular, which
    happens when slope_var is 0 (the slope never varies).
    """
    a, b, c, d = M[..., 0, 0], M[..., 0, 1], M[..., 1, 0], M[..., 1, 1]
    det = a * d - b * c
    ok = det > 1e-12 * np.abs(a * d)
    safe_det = np.where(ok, det, 1.0)
    inv = np.zeros_like(M)
    inv[..., 0, 0] = np.where(ok, d / safe_det, np.where(a > 0, 1.0 / np.where(a > 0, a, 1.0), 0.0))
    inv[..., 1, 1] = np.where(ok, a / safe_det, np.where(d > 0, 1.0 / np.where(d > 0, d, 1.0), 0.0))
    inv[..., 0, 1] = np.where(ok, -b / safe_det, 0.0)
    inv[..., 1, 0] = np.where(ok, -c / safe_det, 0.0)
    return inv


def rts_smoother(
    x_pred: np.ndarray,
    P_pred: np.ndarray,
    x_filt: np.ndarray,
    P_filt: np.ndarray,
    params: ModelParams,
) -> tuple[np.ndarray, np.ndarray]:
    """Run the Rauch-Tung-Striebel backward pass on Kalman filter output."""
    F = params.transition()
    x_smooth = x_filt.copy()
    P_smooth = P_filt.copy()
    for a in range(x_filt.shape[1] - 2, -1, -1):
        C = P_filt[:, a] @ F.T @ _inv2(P_pred[:, a + 1])
        x_smooth[:, a] = x_filt[:, a] + np.einsum("nij,nj->ni", C, x_smooth[:, a + 1] - x_pred[:, a + 1])
        P_smooth[:, a] = P_filt[:, a] + C @ (P_smooth[:, a + 1] - P_pred[:, a + 1]) @ np.swapaxes(C, 1, 2)
    return x_smooth, P_smooth


def kalman_smoother(
    z: np.ndarray,
    R: np.ndarray,
    mask: np.ndarray,
    params: ModelParams,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Run Kalman filter and RTS smoother.

    Returns:
        Tuple of (state_smooth, cov_smooth, loglik per row).
    """
    x_pred, P_pred, x_filt, P_filt, loglik = kalman_filter(z, R, mask, params)
    x_smooth, P_smooth = rts_smoother(x_pred, P_pred, x_filt, P_filt, params)
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
    """Unnormalized log posterior of each row's latent log-rate path."""
    obs, _, _ = poisson_terms(Y, E * np.exp(x), trunc)
    # Filtering the path itself with zero observation noise gives its prior density
    _, _, _, _, log_prior = kalman_filter(x, np.zeros_like(x), mask, params)
    return np.where(mask, obs, 0.0).sum(axis=1) + log_prior


def poisson_laplace(
    Y: np.ndarray,
    E: np.ndarray,
    mask: np.ndarray,
    trunc: np.ndarray,
    params: ModelParams,
    tol: float = 1e-8,
    max_iter: int = 100,
    init_x: np.ndarray | None = None,
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
        init_x: Starting log-rate path, e.g. the mode from nearby
            hyperparameters (the mode itself doesn't depend on it).

    Returns:
        LaplaceResult with mode, variances and per-paper log-likelihood.
    """
    with np.errstate(over="ignore", under="ignore", divide="ignore", invalid="ignore"):
        if init_x is None:
            init_x = np.log((Y + 0.5) / E)
        x = np.where(mask, init_x, 0.0)
        objective = log_posterior(x, Y, E, mask, trunc, params)

        n_iter = 0
        for n_iter in range(1, max_iter + 1):
            _, score, info = poisson_terms(Y, E * np.exp(x), trunc)
            info = np.maximum(info, 1e-12)
            state, _, _ = kalman_smoother(x + score / info, 1.0 / info, mask, params)
            x_new = np.where(mask, state[:, :, 0], 0.0)

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
        state, state_cov, gaussian_loglik = kalman_smoother(z, R, mask, params)

        gaussian_obs = -0.5 * (LOG_2PI + np.log(R) + (z - x) ** 2 / R)
        correction = np.where(mask, obs - gaussian_obs, 0.0).sum(axis=1)

    return LaplaceResult(
        x=x,
        P=state_cov[:, :, 0, 0],
        state=state,
        state_cov=state_cov,
        loglik=gaussian_loglik + correction,
        n_iter=n_iter,
    )


def propagate(
    mean: np.ndarray,
    cov: np.ndarray,
    ages: np.ndarray,
    params: ModelParams,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Project (x, d) forward without observations.

    Args:
        mean: State means, (n_papers, 2).
        cov: State covariances, (n_papers, 2, 2).
        ages: Each paper's age at the starting state.
        params: Model hyperparameters.
        horizon: Number of years to project.

    Returns:
        Tuple of (log-rate means, log-rate variances), each shaped
        (n_papers, horizon + 1); column 0 is the starting state.
    """
    F = params.transition()
    Q = params.noise_cov()
    drift = params.drift_by_age(int(np.max(ages)) + horizon + 1)

    means = np.zeros((len(ages), horizon + 1))
    variances = np.zeros((len(ages), horizon + 1))
    means[:, 0] = mean[:, 0]
    variances[:, 0] = cov[:, 0, 0]
    for h in range(1, horizon + 1):
        mean = mean @ F.T
        mean[:, 0] += drift[ages + h]
        cov = F @ cov @ F.T + Q
        means[:, h] = mean[:, 0]
        variances[:, h] = cov[:, 0, 0]
    return means, variances
