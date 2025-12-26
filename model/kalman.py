"""1D Kalman filter and RTS smoother for citation rate analysis.

Implements a local-level (random walk) state-space model:
- State evolution: x_t = x_{t-1} + epsilon_t, epsilon_t ~ N(0, Q)
- Observation: z_t = x_t + eta_t, eta_t ~ N(0, R_t)

Supports time-varying observation variance for Poisson-like count data.
"""

from __future__ import annotations

from typing import Union

import numpy as np


def compute_obs_variance(
    empirical_rate: np.ndarray,
    overdispersion: float = 1.0,
    min_count: float = 0.5,
    sigma_min_sq: float = 0.01,
) -> np.ndarray:
    """Compute time-varying observation variance based on Poisson approximation.

    For Poisson counts, Var(log y) ≈ 1/λ. We use:
        R_t = φ * (1 / (rate + min_count)) + σ_min²

    Args:
        empirical_rate: Annualized citation rates per year.
        overdispersion: Global overdispersion factor φ (≥1 for overdispersed data).
        min_count: Pseudocount to avoid division by zero.
        sigma_min_sq: Floor variance to prevent R_t from getting too small.

    Returns:
        Array of observation variances R_t for each time point.
    """
    base_R = 1.0 / (empirical_rate + min_count)
    R_t = overdispersion * base_R + sigma_min_sq
    return R_t


def kalman_filter_1d(
    z: np.ndarray,
    process_var: float,
    obs_var: Union[float, np.ndarray],
    x0_mean: float,
    x0_var: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    """Run Kalman filter (forward pass only) and compute log-likelihood.

    Args:
        z: Observations (log-transformed annualized rates).
        process_var: Process variance Q for random walk.
        obs_var: Observation variance R (scalar or array for time-varying).
        x0_mean: Initial state mean.
        x0_var: Initial state variance.

    Returns:
        Tuple of (x_pred, P_pred, x_filt, P_filt, log_likelihood).
    """
    T = len(z)
    if T == 0:
        return np.array([]), np.array([]), np.array([]), np.array([]), 0.0

    # Handle scalar or array obs_var
    if np.isscalar(obs_var):
        R = np.full(T, obs_var)
    else:
        R = np.asarray(obs_var)

    # Model parameters
    F = 1.0  # State transition
    H = 1.0  # Observation matrix
    Q = process_var

    # Storage
    x_pred = np.zeros(T)
    P_pred = np.zeros(T)
    x_filt = np.zeros(T)
    P_filt = np.zeros(T)

    # Log-likelihood accumulator
    log_lik = 0.0

    # Forward pass (Kalman filter)
    for t in range(T):
        if t == 0:
            # Initialize with prior
            x_pred[t] = x0_mean
            P_pred[t] = x0_var
        else:
            # Predict
            x_pred[t] = F * x_filt[t - 1]
            P_pred[t] = F * P_filt[t - 1] * F + Q

        # Innovation (prediction error)
        v_t = z[t] - H * x_pred[t]
        S_t = H * P_pred[t] * H + R[t]  # Innovation variance

        # Accumulate log-likelihood
        # log p(z_t | z_{1:t-1}) = -0.5 * (log(2π) + log(S_t) + v_t²/S_t)
        log_lik += -0.5 * (np.log(2 * np.pi) + np.log(S_t) + v_t**2 / S_t)

        # Update
        K_t = P_pred[t] * H / S_t  # Kalman gain
        x_filt[t] = x_pred[t] + K_t * v_t
        P_filt[t] = (1 - K_t * H) * P_pred[t]

    return x_pred, P_pred, x_filt, P_filt, log_lik


def kalman_smoother_1d(
    z: np.ndarray,
    process_var: float,
    obs_var: Union[float, np.ndarray],
    x0_mean: float,
    x0_var: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Run Kalman filter and RTS smoother on 1D time series.

    Args:
        z: Observations (log-transformed annualized rates).
        process_var: Process variance Q for random walk.
        obs_var: Observation variance R (scalar or array for time-varying).
        x0_mean: Initial state mean.
        x0_var: Initial state variance.

    Returns:
        Tuple of (x_smooth, P_smooth) arrays with smoothed states and variances.
    """
    T = len(z)
    if T == 0:
        return np.array([]), np.array([])

    # Run forward pass
    x_pred, P_pred, x_filt, P_filt, _ = kalman_filter_1d(
        z, process_var, obs_var, x0_mean, x0_var
    )

    # Backward pass (Rauch-Tung-Striebel smoother)
    F = 1.0
    x_smooth = np.zeros(T)
    P_smooth = np.zeros(T)

    # Initialize at final time
    x_smooth[T - 1] = x_filt[T - 1]
    P_smooth[T - 1] = P_filt[T - 1]

    # Backward recursion
    for t in range(T - 2, -1, -1):
        C_t = P_filt[t] * F / P_pred[t + 1]
        x_smooth[t] = x_filt[t] + C_t * (x_smooth[t + 1] - x_pred[t + 1])
        P_smooth[t] = P_filt[t] + C_t**2 * (P_smooth[t + 1] - P_pred[t + 1])

    return x_smooth, P_smooth


def kalman_smoother_with_likelihood(
    z: np.ndarray,
    process_var: float,
    obs_var: Union[float, np.ndarray],
    x0_mean: float,
    x0_var: float = 1.0,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Run Kalman smoother and also return log-likelihood.

    Args:
        z: Observations (log-transformed annualized rates).
        process_var: Process variance Q for random walk.
        obs_var: Observation variance R (scalar or array for time-varying).
        x0_mean: Initial state mean.
        x0_var: Initial state variance.

    Returns:
        Tuple of (x_smooth, P_smooth, log_likelihood).
    """
    T = len(z)
    if T == 0:
        return np.array([]), np.array([]), 0.0

    # Run forward pass
    x_pred, P_pred, x_filt, P_filt, log_lik = kalman_filter_1d(
        z, process_var, obs_var, x0_mean, x0_var
    )

    # Backward pass (Rauch-Tung-Striebel smoother)
    F = 1.0
    x_smooth = np.zeros(T)
    P_smooth = np.zeros(T)

    x_smooth[T - 1] = x_filt[T - 1]
    P_smooth[T - 1] = P_filt[T - 1]

    for t in range(T - 2, -1, -1):
        C_t = P_filt[t] * F / P_pred[t + 1]
        x_smooth[t] = x_filt[t] + C_t * (x_smooth[t + 1] - x_pred[t + 1])
        P_smooth[t] = P_filt[t] + C_t**2 * (P_smooth[t + 1] - P_pred[t + 1])

    return x_smooth, P_smooth, log_lik
