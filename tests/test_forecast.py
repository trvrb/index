from datetime import datetime, timezone

import numpy as np
import pytest

from model.data import build_series, h_index, to_arrays
from model.forecast import aggregate_summary, forecast_horizon, paper_summaries, simulate
from model.kalman import ModelParams, poisson_laplace

SCRAPED_AT = datetime(2024, 7, 2, tzinfo=timezone.utc)
PARAMS = ModelParams(process_var=0.15, init_mean=1.0, init_var=1.0, drift=[1.0, 0.5, -0.1])

PAPERS = [
    {"title": "A", "total_citations": 60, "citations_by_year": {"2019": 5, "2020": 12, "2021": 15, "2022": 12, "2023": 9, "2024": 4}},
    {"title": "B", "total_citations": 30, "citations_by_year": {"2021": 4, "2022": 8, "2023": 10, "2024": 6}},
    {"title": "C", "total_citations": 3, "citations_by_year": {"2024": 2}},
]


def _forecast(seed=0):
    series = [build_series(p, SCRAPED_AT) for p in PAPERS]
    Y, E, mask, trunc = to_arrays(series)
    laplace = poisson_laplace(Y, E, mask, trunc, PARAMS)
    return series, simulate(series, laplace, PARAMS, 2024, horizon=3, n_samples=500, seed=seed)


def test_reproducible_with_seed():
    _, a = _forecast(seed=3)
    _, b = _forecast(seed=3)
    assert aggregate_summary(a) == aggregate_summary(b)
    assert paper_summaries(a) == paper_summaries(b)


def test_year_end_projection_includes_observed():
    series, forecast = _forecast()
    observed = np.array([s.counts[-1] for s in series])
    assert forecast.years == [2024, 2025, 2026, 2027]
    assert np.all(forecast.counts[:, :, 0] >= observed)
    assert np.all(np.diff(forecast.cumulative, axis=2) >= 0)


def test_h_index_projection_not_below_today():
    _, forecast = _forecast()
    today = h_index(np.array([p["total_citations"] for p in PAPERS]))
    assert aggregate_summary(forecast)["h_index_q10"][0] >= today


def test_drift_uses_target_age():
    series, forecast = _forecast()
    steps = np.diff(forecast.log_rate_mean, axis=1)
    # Paper C is in its first year (age 0), so its next steps are ages 1, 2, 3
    np.testing.assert_allclose(steps[2], [1.0, 0.5, -0.1])
    # Paper A is at age 5, past the last drift age
    np.testing.assert_allclose(steps[0], [-0.1, -0.1, -0.1])
    np.testing.assert_allclose(np.diff(forecast.log_rate_var[0]), PARAMS.process_var)


def test_rate_quantiles_ordered():
    _, forecast = _forecast()
    for summary in paper_summaries(forecast):
        assert np.all(np.array(summary["rate_q10"]) < np.array(summary["rate_q50"]))
        assert np.all(np.array(summary["rate_q50"]) < np.array(summary["rate_q90"]))
        assert summary["cumulative_q50"][0] >= 0


def test_momentum_carries_recent_trend():
    params = ModelParams(process_var=0.03, init_mean=1.0, init_var=1.0, drift=[1.0, 0.0, -0.1],
                         slope_var=0.07, persistence=0.5)
    flat = {str(y): 40 for y in range(2015, 2022)}
    papers = [
        {"title": "Rising", "citations_by_year": {**flat, "2022": 60, "2023": 90, "2024": 60}},
        {"title": "Falling", "citations_by_year": {**flat, "2022": 25, "2023": 15, "2024": 4}},
    ]
    series = [build_series(p, SCRAPED_AT) for p in papers]
    Y, E, mask, trunc = to_arrays(series)
    laplace = poisson_laplace(Y, E, mask, trunc, params)
    forecast = simulate(series, laplace, params, 2024, horizon=3, n_samples=10, seed=0)

    steps = np.diff(forecast.log_rate_mean, axis=1)
    deviation = steps - (-0.1)  # both papers are past the last drift age
    assert np.all(deviation[0] > 0) and np.all(deviation[1] < 0)
    # Momentum fades by rho each year
    np.testing.assert_allclose(deviation[:, 1:] / deviation[:, :-1], 0.5)


@pytest.mark.parametrize(
    "exposure, lead, horizon",
    [(0.1, 1.5, 0), (0.49, 1.5, 0), (0.5, 1.5, 1), (0.78, 1.5, 1), (1.0, 1.5, 1), (0.3, 3.0, 2)],
)
def test_forecast_horizon(exposure, lead, horizon):
    # Before July a 1.5-year lead reaches the end of this year; from July on, next year
    assert forecast_horizon(exposure, lead) == horizon
