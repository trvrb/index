import numpy as np
import pytest
from scipy.optimize import minimize
from scipy.special import gammaln
from scipy.stats import multivariate_normal

from model.kalman import ModelParams, kalman_smoother, log_posterior, poisson_laplace

PARAMS = ModelParams(process_var=0.2, init_mean=1.0, init_var=1.5, drift=[0.8, -0.1])


def scalar_smoother(z, R, params):
    """Reference scalar Kalman filter and RTS smoother."""
    T = len(z)
    drift = params.drift_by_age(T)
    xp, Pp, xf, Pf = (np.zeros(T) for _ in range(4))
    loglik = 0.0
    for t in range(T):
        if t == 0:
            xp[t], Pp[t] = params.init_mean, params.init_var
        else:
            xp[t], Pp[t] = xf[t - 1] + drift[t], Pf[t - 1] + params.process_var
        S = Pp[t] + R[t]
        K = Pp[t] / S
        xf[t] = xp[t] + K * (z[t] - xp[t])
        Pf[t] = (1 - K) * Pp[t]
        loglik += -0.5 * (np.log(2 * np.pi * S) + (z[t] - xp[t]) ** 2 / S)
    xs, Ps = xf.copy(), Pf.copy()
    for t in range(T - 2, -1, -1):
        C = Pf[t] / Pp[t + 1]
        xs[t] = xf[t] + C * (xs[t + 1] - xp[t + 1])
        Ps[t] = Pf[t] + C**2 * (Ps[t + 1] - Pp[t + 1])
    return xs, Ps, loglik


def test_batched_smoother_matches_scalar_reference():
    rng = np.random.default_rng(1)
    lengths = [1, 4, 7]
    z = rng.normal(size=(3, 7))
    R = rng.uniform(0.1, 2.0, size=(3, 7))
    mask = np.arange(7)[None, :] < np.array(lengths)[:, None]

    xs, Ps, loglik = kalman_smoother(z, R, mask, PARAMS)
    for i, n in enumerate(lengths):
        ref_x, ref_P, ref_ll = scalar_smoother(z[i, :n], R[i, :n], PARAMS)
        np.testing.assert_allclose(xs[i, :n], ref_x)
        np.testing.assert_allclose(Ps[i, :n], ref_P)
        assert loglik[i] == pytest.approx(ref_ll)


def test_filter_loglik_matches_multivariate_normal():
    T = 5
    z = np.array([[0.3, 1.2, 2.5, 2.0, 1.8]])
    R = np.array([[0.5, 0.2, 0.3, 0.4, 0.1]])
    _, _, loglik = kalman_smoother(z, R, np.ones((1, T), dtype=bool), PARAMS)

    # x_t = x_0 + sum of drifts and steps, so Cov(x_s, x_t) = v0 + q * min(s, t)
    drift = PARAMS.drift_by_age(T)
    mean = PARAMS.init_mean + np.cumsum(drift)
    ages = np.arange(T)
    cov = PARAMS.init_var + PARAMS.process_var * np.minimum.outer(ages, ages) + np.diag(R[0])
    assert loglik[0] == pytest.approx(multivariate_normal(mean, cov).logpdf(z[0]))


def _one_series(counts, exposure=None, truncated=False):
    Y = np.array([counts], dtype=float)
    E = np.ones_like(Y) if exposure is None else np.array([exposure])
    mask = np.ones_like(Y, dtype=bool)
    trunc = np.zeros_like(mask)
    trunc[0, 0] = truncated
    return Y, E, mask, trunc


@pytest.mark.parametrize("truncated", [False, True])
def test_laplace_mode_and_variance(truncated):
    Y, E, mask, trunc = _one_series([2, 7, 0, 3, 1], [1, 1, 1, 1, 0.4], truncated)
    result = poisson_laplace(Y, E, mask, trunc, PARAMS)

    def neg_log_post(x):
        return -log_posterior(x[None, :], Y, E, mask, trunc, PARAMS)[0]

    direct = minimize(neg_log_post, np.zeros(5), method="BFGS", options={"gtol": 1e-10})
    np.testing.assert_allclose(result.x[0], direct.x, atol=1e-5)

    # Posterior variance is the diagonal of the inverse negative Hessian
    eps = 1e-4
    hessian = np.zeros((5, 5))
    for i in range(5):
        for j in range(5):
            ei, ej = np.eye(5)[i] * eps, np.eye(5)[j] * eps
            x = result.x[0]
            hessian[i, j] = (
                neg_log_post(x + ei + ej) - neg_log_post(x + ei - ej)
                - neg_log_post(x - ei + ej) + neg_log_post(x - ei - ej)
            ) / (4 * eps**2)
    np.testing.assert_allclose(result.P[0], np.diag(np.linalg.inv(hessian)), rtol=1e-3)


def test_laplace_likelihood_matches_quadrature():
    # Laplace is accurate when counts are large
    counts = np.array([200.0, 300.0])
    Y, E, mask, trunc = _one_series(counts)
    params = ModelParams(process_var=0.3, init_mean=5.0, init_var=1.0, drift=[0.2])
    result = poisson_laplace(Y, E, mask, trunc, params)

    grid = [np.linspace(m - 8 * np.sqrt(v), m + 8 * np.sqrt(v), 801)
            for m, v in zip(result.x[0], result.P[0])]
    x0, x1 = np.meshgrid(*grid, indexing="ij")
    log_prior = (
        -0.5 * (np.log(2 * np.pi * params.init_var) + (x0 - params.init_mean) ** 2 / params.init_var)
        - 0.5 * (np.log(2 * np.pi * params.process_var) + (x1 - x0 - 0.2) ** 2 / params.process_var)
    )
    log_lik = sum(c * x - np.exp(x) - gammaln(c + 1) for c, x in zip(counts, (x0, x1)))
    log_joint = log_prior + log_lik
    cell = (grid[0][1] - grid[0][0]) * (grid[1][1] - grid[1][0])
    exact = np.log(np.exp(log_joint - log_joint.max()).sum() * cell) + log_joint.max()

    assert result.loglik[0] == pytest.approx(exact, abs=5e-3)


def test_zero_counts_pull_rate_down():
    high = poisson_laplace(*_one_series([5, 5, 5, 5, 5]), PARAMS)
    trailing_zeros = poisson_laplace(*_one_series([5, 5, 5, 0, 0]), PARAMS)
    assert trailing_zeros.x[0, -1] < high.x[0, -1] - 1.0
