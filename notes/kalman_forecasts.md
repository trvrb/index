# Forecast extension for `index.rates`

## 1. Goal

Extend the existing Kalman-based analysis in `index.rates` to:

* **Forecast per-year citation rates** for each paper **H years into the future**, where H is configurable (e.g. `--forecast-years 5`).
* Use the **same process volatility** (`process_var = q`) already estimated from data to drive how fast uncertainty grows.
* Optionally provide:

  * forecasts on the **log-rate** scale,
  * **median**, **mean**, and **standard deviation** of the rate in future years.

We keep the existing model (random walk on log rates with heteroscedastic observation noise); forecasting is just the prediction step of that state-space model pushed into the future.

---

## 2. CLI changes

In `rates.py`, add:

* `--forecast-years N` (integer, default `0`)

Example usage:

```bash
python -m model.rates \
  --input citations.json \
  --output citation_rates.json \
  --process-var 0.7 \
  --obs-overdispersion 1.5 \
  --forecast-years 5
```

Behavior:

* If `--forecast-years 0` (or omitted), **no forecasting** is performed (current behavior).
* If `--forecast-years > 0`, each paper in the output includes **H future years** of forecasted rates.

---

## 3. Model recap (what we already have)

For each paper:

* Observed annualized rate (per-year citation rate):

  * Years: `t = 1..T` (e.g., 2018–2025).
  * Counts: `y_t` (citations in year t).
  * Exposure: `e_t` (fraction of year observed; 1 for complete years, <1 for current partial year).
  * Empirical rate: `r_t = y_t / e_t`.

* Transform to **log-rate**:

  ```python
  z_t = log(r_t + min_count)
  ```

* State-space model on **log-rate**:

  * State: `x_t = log λ_t` (latent log citation rate).

  * Evolution (random walk):

    [
    x_t = x_{t-1} + \epsilon_t, \quad \epsilon_t \sim \mathcal{N}(0, q)
    ]

    where `q = process_var`.

  * Observation:

    [
    z_t = x_t + \eta_t, \quad \eta_t \sim \mathcal{N}(0, R_t)
    ]

    where `R_t` may be **time-varying**, e.g.:

    ```python
    # current implementation idea:
    base_R_t ≈ 1 / (empirical_rate_t + min_count)
    R_t = phi * base_R_t + sigma_min**2
    ```

    with global `phi = obs_overdispersion`, `sigma_min` small (e.g., 0.1).

* We already run a **Kalman filter + RTS smoother** and get:

  * `x_smooth[t]` – smoothed mean of state at year t.
  * `P_smooth[t]` – smoothed variance at year t.

These smoothed estimates use **all historical information** and are therefore the right starting point for forecasting into the future.

---

## 4. Forecasting in the Kalman framework

Forecasting is just repeatedly applying the **state evolution** without observations.

### 4.1 Forecast horizon

Let:

* Observed years: `years = [y₁, y₂, ..., y_T]` (e.g. 2018..2025).
* Last observed calendar year: `last_year = years[-1]`.
* Forecast horizon: `H = forecast_years`.

Define future years:

```python
forecast_years = [last_year + h for h in range(1, H + 1)]
```

We assume **full-year exposure** for future years (i.e., we’re forecasting full calendar-year rates).

### 4.2 State forecast on log-rate scale

From the RTS smoother we already have:

* `m_T = x_smooth[T-1]` (using 0-based indexing for Python).
* `C_T = P_smooth[T-1]`.

For a random walk with variance `q` and F = 1:

* One-step-ahead forecast:

  [
  x_{T+1 \mid T} = m_T,\quad
  C_{T+1 \mid T} = C_T + q
  ]

* Two-step-ahead forecast:

  [
  x_{T+2 \mid T} = m_T,\quad
  C_{T+2 \mid T} = C_T + 2q
  ]

* In general, for horizon `h = 1..H`:

  [
  x_{T+h \mid T} \sim \mathcal{N}\left(m_T,; C_T + h q\right)
  ]

Implementation sketch:

```python
forecast_log_mean = []
forecast_log_var = []

m = x_smooth[-1]      # m_T
C = P_smooth[-1]      # C_T

for h in range(1, H + 1):
    var_h = C + h * process_var  # C_T + h*q
    mean_h = m                   # stays constant under pure random walk

    forecast_log_mean.append(mean_h)
    forecast_log_var.append(var_h)
```

No updates are done in the absence of observations; this is pure prediction.

---

## 5. Transforming forecasts to rates (and counts)

We want **future citation rates** (λ) rather than log-rates.

Given:

* `x_{T+h}` ~ N(mean_h, var_h).

Then `λ_{T+h} = exp(x_{T+h})` is lognormally distributed.

Useful quantities:

* **Median rate**:

  [
  \text{median}(\lambda_{T+h}) = \exp(\text{mean}_h)
  ]

* **Mean rate**:

  [
  \mathbb{E}[\lambda_{T+h}]
  = \exp\left(\text{mean}_h + \tfrac12 \text{var}_h\right)
  ]

* **Variance of rate**:

  [
  \mathrm{Var}(\lambda_{T+h})
  = \left(\exp(\text{var}_h) - 1\right)
  \exp\left(2 \text{mean}_h + \text{var}_h\right)
  ]

* **Standard deviation of rate**:

  ```python
  std_lambda_h = math.sqrt(var_lambda_h)
  ```

Implementation sketch:

```python
forecast_rate_median = []
forecast_rate_mean = []
forecast_rate_std = []

for mean_h, var_h in zip(forecast_log_mean, forecast_log_var):
    median_lambda = math.exp(mean_h)
    mean_lambda = math.exp(mean_h + 0.5 * var_h)
    var_lambda = (math.exp(var_h) - 1.0) * math.exp(2 * mean_h + var_h)
    std_lambda = math.sqrt(var_lambda)

    forecast_rate_median.append(median_lambda)
    forecast_rate_mean.append(mean_lambda)
    forecast_rate_std.append(std_lambda)
```

You can choose which of these to present as “the” forecast. A reasonable default:

* Use `forecast_rate_mean` as the **forecasted rate**,
* Use `forecast_rate_std` for uncertainty bands,
* Optionally include `median` as well.

### Optional: Forecast counts

If you want predicted **counts** rather than just rates, assume:

* Future exposure `e_{T+h} = 1.0` (full year).
* Given λ, y ~ Poisson(λ).
* Unconditionally:

  * `E[y_{T+h}] = E[λ_{T+h}] = mean_lambda`.
  * `Var(y_{T+h}) = E[λ_{T+h}] + Var(λ_{T+h})`.

So:

```python
forecast_counts_mean = forecast_rate_mean  # exposure = 1
forecast_counts_var = [
    m + (s**2)               # approx: mean + var of λ
    for m, s in zip(forecast_rate_mean, forecast_rate_std)
]
forecast_counts_std = [math.sqrt(v) for v in forecast_counts_var]
```

This is optional; you may only need rates.

---

## 6. Output JSON schema extension

Per paper, add forecast fields when `H > 0`.

Current per-paper structure (simplified):

```jsonc
{
  "title": "...",
  "years": [...],
  "observed_citations": [...],
  "exposure_fraction": [...],
  "empirical_rate": [...],
  "smoothed_rate": [...],
  "smoothed_log_rate": [...],
  "smoothed_rate_std": [...]
}
```

Extend with:

```jsonc
{
  "forecast_years": [2026, 2027, ...],

  "forecast_log_rate_mean": [...],   // x_{T+h|T} means
  "forecast_log_rate_var": [...],    // C_T + h*q

  "forecast_rate_median": [...],     // exp(mean)
  "forecast_rate_mean": [...],       // exp(mean + 0.5*var)
  "forecast_rate_std": [...],        // sqrt(var of λ)

  "forecast_counts_mean": [...],     // optional
  "forecast_counts_std": [...]       // optional
}
```

If `forecast_years == 0`, you can either omit these keys or include them as empty lists for simplicity/consistency.

At the top level, document the forecast settings:

```jsonc
"forecast": {
  "horizon_years": H,
  "assumptions": {
    "model": "random_walk_log_rate",
    "process_var": q,
    "obs_overdispersion": phi,
    "min_count": min_count
  }
}
```

---

## 7. Integration into the existing `analyze_paper` pipeline

In your `analyze_paper` function (from the previous design):

1. Run existing steps:

   * build `years`, `counts`, `exposure`.
   * compute `empirical_rate`.
   * compute `z_t`.
   * run `kalman_smoother_1d(...)` to get `x_smooth`, `P_smooth`.
   * back-transform to `smoothed_rate`, `smoothed_rate_std`.

2. **If `forecast_years > 0`:**

   * Compute `forecast_years`.

   * Use the last smoothed state to compute:

     ```python
     x_T = x_smooth[-1]
     P_T = P_smooth[-1]
     ```

   * Loop `h = 1..H` to compute `forecast_log_mean`, `forecast_log_var`.

   * Compute `forecast_rate_median / mean / std` via lognormal formulas.

   * Optionally compute counts forecast.

3. Add these forecast arrays to the returned dict for the paper.

Pseudocode snippet:

```python
def analyze_paper(..., forecast_years=0, process_var=..., ...):
    ...
    x_smooth, P_smooth = kalman_smoother_1d(...)
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
        "smoothed_rate_std": smoothed_std.tolist()
    }

    if forecast_years > 0:
        last_year = years[-1]
        forecast_years_list = [last_year + h for h in range(1, forecast_years + 1)]

        x_T = x_smooth[-1]
        P_T = P_smooth[-1]

        f_log_mean = []
        f_log_var = []
        f_rate_median = []
        f_rate_mean = []
        f_rate_std = []

        for h in range(1, forecast_years + 1):
            var_h = P_T + h * process_var
            mean_h = x_T

            f_log_mean.append(mean_h)
            f_log_var.append(var_h)

            median_lambda = math.exp(mean_h)
            mean_lambda = math.exp(mean_h + 0.5 * var_h)
            var_lambda = (math.exp(var_h) - 1.0) * math.exp(2 * mean_h + var_h)
            std_lambda = math.sqrt(var_lambda)

            f_rate_median.append(median_lambda)
            f_rate_mean.append(mean_lambda)
            f_rate_std.append(std_lambda)

        result.update({
            "forecast_years": forecast_years_list,
            "forecast_log_rate_mean": f_log_mean,
            "forecast_log_rate_var": f_log_var,
            "forecast_rate_median": f_rate_median,
            "forecast_rate_mean": f_rate_mean,
            "forecast_rate_std": f_rate_std
        })

        # Optional counts:
        # result["forecast_counts_mean"] = f_rate_mean
        # result["forecast_counts_std"] = ...
    return result
```

The top-level CLI just needs to pass `forecast_years` through to `analyze_paper`.

---

## 8. Sanity checks and caveats

**Checks:**

* For `H = 0`, output should be identical to the pre-forecast version.
* As `H` increases:

  * Forecast **log-rate mean** stays near the last smoothed value (random walk has no trend).
  * **Uncertainty** (`forecast_log_rate_var` and `forecast_rate_std`) **grows roughly like sqrt(h)** on the rate scale.

**Interpretation / caveats:**

* The model assumes **no systematic trend** beyond what’s already baked into the last state. It’s “driftless” on the log scale; long-term growth/decline comes only from the current level plus noise.
* For extremely volatile papers (like Nextstrain), the process variance `q` will cause forecast uncertainty to grow quickly — as it should.
