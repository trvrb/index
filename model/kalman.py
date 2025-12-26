"""1D Kalman filter and RTS smoother for citation rate analysis.

Implements a local-level (random walk) state-space model:
- State evolution: x_t = x_{t-1} + epsilon_t, epsilon_t ~ N(0, Q)
- Observation: z_t = x_t + eta_t, eta_t ~ N(0, R)
"""

from __future__ import annotations

import numpy as np


def kalman_smoother_1d(
    z: np.ndarray,
    process_var: float,
    obs_var: float,
    x0_mean: float,
    x0_var: float = 1.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Run Kalman filter and RTS smoother on 1D time series.

    Args:
        z: Observations (log-transformed annualized rates).
        process_var: Process variance Q for random walk.
        obs_var: Observation variance R.
        x0_mean: Initial state mean.
        x0_var: Initial state variance.

    Returns:
        Tuple of (x_smooth, P_smooth) arrays with smoothed states and variances.
    """
    T = len(z)
    if T == 0:
        return np.array([]), np.array([])

    # Model parameters (scalar case)
    F = 1.0  # State transition
    H = 1.0  # Observation matrix
    Q = process_var
    R = obs_var

    # Storage for filter pass
    x_pred = np.zeros(T)
    P_pred = np.zeros(T)
    x_filt = np.zeros(T)
    P_filt = np.zeros(T)

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

        # Update with observation
        K_t = P_pred[t] * H / (H * P_pred[t] * H + R)  # Kalman gain
        x_filt[t] = x_pred[t] + K_t * (z[t] - H * x_pred[t])
        P_filt[t] = (1 - K_t * H) * P_pred[t]

    # Backward pass (Rauch-Tung-Striebel smoother)
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
