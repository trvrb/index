# Design doc: `index` citation-rate analysis CLI

This document specifies a second Python command-line tool for the `index` repository. The tool consumes `citations.json` (as produced by the existing scraper) and produces:

1. **Empirical** per-year citation rates for each paper.
2. **Smoothed** per-year citation rate estimates using a simple **state-space (Kalman) model**.

---

## 1. High-level overview

### Input

* A single JSON file, `citations.json`, with structure:

```jsonc
{
  "user_id": "RIi-1pAAAAAJ",
  "scraped_at": "2025-12-25T23:43:11.420360+00:00",
  "papers": [
    {
      "title": "Nextstrain: real-time tracking of pathogen evolution",
      "total_citations": 3638,
      "citations_by_year": {
        "2018": 20,
        "2019": 60,
        ...
        "2025": 419
      }
    },
    ...
  ]
}
```

### Output (proposed)

A JSON file, e.g. `citation_rates.json`, of the form:

```jsonc
{
  "user_id": "RIi-1pAAAAAJ",
  "scraped_at": "...same as input...",
  "papers": [
    {
      "title": "...",
      "years": [2018, 2019, ..., 2025],
      "observed_citations": [20, 60, ..., 419],
      "exposure_fraction": [1.0, 1.0, ..., 0.986],        // fraction of year observed
      "empirical_rate": [20.0, 60.0, ..., 425.1],         // observed / exposure
      "smoothed_rate": [λ̂_2018, λ̂_2019, ..., λ̂_2025],   // from Kalman smoother
      "smoothed_log_rate": [..optional..],
      "smoothed_rate_std": [σ_2018, σ_2019, ..., σ_2025]  // optional uncertainty
    },
    ...
  ]
}
```

This output is then usable to:

* Compute **h-index trajectories** over years using smoothed or empirical counts.
* Plot per-paper citation rate curves.
* Aggregate to yearly citation intensity for the whole corpus.

---

## 2. CLI interface

Add a second CLI entrypoint alongside whatever exists for scraping. For concreteness:

### Command

```bash
python -m model/rates \
  --input results/citations.json \
  --output results/citation_rates.json \
  --model kalman \
  --process-var 0.15 \
  --obs-var 0.3
```

### Arguments

* `--input PATH` (required): path to `citations.json`.
* `--output PATH` (required): path for output JSON.
* `--model {kalman}` (optional, default `kalman`):

  * Leave room to later add `gp` (Gaussian process).
* `--process-var FLOAT` (optional, default `0.15`):

  * Process variance on the **log-rate** random walk (see model).
* `--obs-var FLOAT` (optional, default `0.3`):

  * Observation noise variance on the **log-transformed counts**.
* `--min-count FLOAT` (optional, default `0.5`):

  * Pseudocount added before log to avoid `log(0)`.

Implementation can use `argparse` or `click`. Error on missing input/output; create/overwrite output.

---

## 3. Data preparation

All of this is per-paper. You’ll want a helper function to transform the raw JSON into a tidy time series.

### 3.1 Parse `scraped_at` and current year

* Parse `scraped_at` into a timezone-aware `datetime`.
* Let `current_year = scraped_at.year`.
* Define:

  * `year_start = datetime(current_year, 1, 1, tzinfo=scraped_at.tzinfo)`
  * `next_year_start = datetime(current_year + 1, 1, 1, tzinfo=scraped_at.tzinfo)`
  * `exposure_fraction_current = (scraped_at - year_start).total_seconds() / (next_year_start - year_start).total_seconds()`

For **all years < current_year**, exposure is assumed to be **1.0** (full year).
For **current_year**, use `exposure_fraction_current` as above.

### 3.2 Construct year grid per paper

For each paper:

1. Extract `citations_by_year` as a `dict[str,int]`.

2. If the dict is empty:

   * Decide on behavior (most reasonable: skip smoothing and store empty arrays).

3. Otherwise:

   * Convert keys to `int` and store `(year, count)` pairs.
   * Let `min_year = min(citation_years)` and `max_year = max(citation_years)`.
   * **Important detail:**
     Do **not** extend the series backwards before `min_year` or beyond `current_year`.
     Use the time grid:

     ```python
     years = sorted(citation_years)
     ```

     * If some years between `min_year` and `max_year` are missing from the dict, treat them as **zero** citations (the paper exists but had zero citations that year).
     * Do **not** assume years before `min_year` are zeros (that’s almost surely pre-publication).

4. Build arrays:

   ```python
   years = np.array(sorted_years, dtype=int)
   counts = np.array([citations_by_year.get(str(y), 0) for y in years], dtype=float)
   exposure = np.ones_like(counts)

   if years[-1] == current_year:
       exposure[-1] = exposure_fraction_current
   ```

### 3.3 Empirical per-year rates

* Define **empirical rate** as:

  ```python
  # avoid division by zero if exposure somehow becomes 0
  empirical_rate = counts / np.maximum(exposure, 1e-6)
  ```

* This “annualizes” the current year’s partial count:

  * E.g., if `2025` has 419 citations by Dec 25 (~0.986 of the year), the empirical rate is about `419 / 0.986 ~ 425`.

These empirical rates are purely descriptive; smoothing is applied afterward.

---

## 4. Statistical model (Kalman smoothing)

We want a simple, robust, **per-paper**, **per-year** model:

* Latent **log citation rate** evolves as a random walk.
* Observed counts are noisy realizations of that rate.

### 4.1 Notation

For a given paper:

* Years: `t = 1, ..., T`, where `T = len(years)`.

* Let `y_t` be the observed **count** in year `t`.

* Let `e_t` be the **exposure fraction** (1 for full years, <1 for current year).

* Define **annualized observation**:

  ```python
  r_t = y_t / e_t
  ```

  This is the empirical annual rate (used for the observation model).

* Define transformed observations on the log scale:

  ```python
  z_t = log(r_t + min_count)
  ```

  where `min_count` is a small pseudocount (e.g., 0.5).

### 4.2 State-space model

We work on the log-rate scale:

* **State (latent log rate)**

  [
  x_t = \log \lambda_t
  ]

* **State evolution (random walk)**

  [
  x_t = x_{t-1} + \epsilon_t, \quad \epsilon_t \sim \mathcal{N}(0, q)
  ]

  where `q = process_var` (e.g., 0.15).

* **Observation model**

  We approximate log-counts with Gaussian noise:

  [
  z_t = x_t + \eta_t, \quad \eta_t \sim \mathcal{N}(0, r)
  ]

  where `r = obs_var` (e.g., 0.3).

So we’re not modeling Poisson counts exactly, but treating the **log annualized rate** as Gaussian with additive noise. Given yearly data and moderate counts, this is reasonable and easy to implement.

### 4.3 Initial conditions

For each paper:

* Initialize `x_1` mean as:

  ```python
  x0_mean = log(r_1 + min_count)
  ```

* Set an initial variance, e.g.:

  ```python
  x0_var = 1.0
  ```

This is not very sensitive as long as the series has more than a couple of years.

### 4.4 Kalman filter & RTS smoother

Because both the state and observation models are linear‐Gaussian, we can use the standard Kalman recursions:

Parameters:

* `F = 1.0`  (state transition scalar)
* `H = 1.0`  (observation scalar)
* `Q = q`    (process variance)
* `R = r`    (observation variance)

#### Forward pass (Kalman filter)

For `t = 1..T`:

* **Predict:**

  ```python
  x_pred[t] = F * x_filt[t-1]
  P_pred[t] = F * P_filt[t-1] * F + Q
  ```

  For `t=1`, use `x_pred[1] = x0_mean`, `P_pred[1] = x0_var`.

* **Update with observation `z_t`:**

  ```python
  K_t = P_pred[t] * H / (H * P_pred[t] * H + R)       # Kalman gain
  x_filt[t] = x_pred[t] + K_t * (z_t - H * x_pred[t])
  P_filt[t] = (1 - K_t * H) * P_pred[t]
  ```

We should handle missing years/observations if needed (e.g. if some year is truly unobserved), but in this pipeline we’re constructing a complete yearly grid and filling missing with zeros, so all `z_t` exist. If you want to treat some years as missing, skip the update step and just use prediction.

#### Backward pass (Rauch–Tung–Striebel smoother)

To get smoothed states `x_smooth[t]` and variances `P_smooth[t]`:

* Initialize:

  ```python
  x_smooth[T] = x_filt[T]
  P_smooth[T] = P_filt[T]
  ```

* For `t = T-1..1` backwards:

  ```python
  C_t = P_filt[t] * F / P_pred[t+1]
  x_smooth[t] = x_filt[t] + C_t * (x_smooth[t+1] - x_pred[t+1])
  P_smooth[t] = P_filt[t] + C_t**2 * (P_smooth[t+1] - P_pred[t+1])
  ```

### 4.5 Back-transform to rates

For each `t`:

* Smoothed log-rate:

  ```python
  x_hat_t = x_smooth[t]
  var_x_t = P_smooth[t]
  ```

* Smoothed rate:

  ```python
  lambda_hat_t = exp(x_hat_t)
  ```

* Approximate standard deviation on rate (delta method, optional):

  ```python
  std_lambda_t = lambda_hat_t * sqrt(var_x_t)
  ```

These `lambda_hat_t` are the **smoothed annual citation rates** for each year, corrected for partial exposure in the final year.

---

## 5. Putting it together: per-paper pipeline

Pseudocode for one paper:

```python
def analyze_paper(paper, scraped_at, process_var, obs_var, min_count):
    # 1. Build year, count, exposure arrays
    citations = paper["citations_by_year"]  # dict str->int
    if not citations:
        return {
            "title": paper["title"],
            "years": [],
            "observed_citations": [],
            "exposure_fraction": [],
            "empirical_rate": [],
            "smoothed_rate": [],
            "smoothed_log_rate": [],
            "smoothed_rate_std": []
        }

    years = sorted(int(y) for y in citations.keys())
    current_year = scraped_at.year

    # Note: we only use years actually present; no extension backwards.
    counts = np.array([citations.get(str(y), 0) for y in years], dtype=float)

    exposure = np.ones_like(counts)
    if years[-1] == current_year:
        exposure[-1] = compute_exposure_fraction(scraped_at)  # as defined above

    # 2. Empirical rates (annualized)
    empirical = counts / np.maximum(exposure, 1e-6)

    # 3. Transform to log space
    z = np.log(empirical + min_count)

    # 4. Kalman smoothing on z_t with local-level model
    x_smooth, P_smooth = kalman_smoother_1d(
        z,
        process_var=process_var,
        obs_var=obs_var,
        x0_mean=z[0],
        x0_var=1.0
    )

    smoothed_log = x_smooth.tolist()
    smoothed_rate = np.exp(x_smooth)
    smoothed_std = smoothed_rate * np.sqrt(P_smooth)

    # 5. Build output object
    return {
        "title": paper["title"],
        "years": years,
        "observed_citations": counts.tolist(),
        "exposure_fraction": exposure.tolist(),
        "empirical_rate": empirical.tolist(),
        "smoothed_rate": smoothed_rate.tolist(),
        "smoothed_log_rate": smoothed_log,
        "smoothed_rate_std": smoothed_std.tolist()
    }
```

Where `kalman_smoother_1d` is a small helper that implements the filter + RTS smoother for a 1D series (as described in §4.4).

---

## 6. Top-level script structure

A reasonable file layout:

```text
index/
  model/
    __init__.py
    rates.py         # CLI entrypoint, orchestrates everything
    kalman.py        # contains kalman_smoother_1d
    io.py            # optional shared JSON I/O helpers
```

### `rates.py` outline

1. Parse CLI arguments.

2. Load `citations.json` into memory.

3. Parse `scraped_at` into `datetime`.

4. Loop over papers, calling `analyze_paper`.

5. Build a top-level result structure:

   ```python
   result = {
       "user_id": data["user_id"],
       "scraped_at": data["scraped_at"],
       "model": {
           "type": "kalman",
           "process_var": process_var,
           "obs_var": obs_var,
           "min_count": min_count
       },
       "papers": analyzed_papers
   }
   ```

6. Write result to `--output` as JSON with reasonable indentation.

---

## 7. Possible Gaussian process extension (optional)

If you later want a GP option (`--model gp`), the structure can be:

* Same `years`, `counts`, `exposure`, `empirical_rate`.

* Define time inputs `t = [0, 1, ..., T-1]` (or actual years shifted).

* Use a 1D GP regression on:

  * Inputs: `t` (float years)
  * Outputs: `log(empirical_rate + min_count)`

* Kernel: e.g., RBF with length-scale ~ 2–4 years plus small white noise.

* Use `sklearn.gaussian_process.GaussianProcessRegressor` to output mean + std at each `t`.

* Exponentiate to get rates.

Interface can reuse the same output structure; only model metadata changes.

---

## 8. Testing & sanity checks

Things worth checking in code:

1. **Mass conservation sanity check:**

   * For each paper, `sum(observed_citations)` should equal `total_citations` in `citations.json`.
   * Log a warning if not.

2. **Current year exposure check:**

   * `0.0 < exposure_fraction_current <= 1.0`.
   * If `scraped_at` is somehow out of year boundaries, fall back to `1.0`.

3. **Visual spot checks (for manual validation):**

   * For a few representative papers:

     * Plot `years` vs `observed_citations` and `smoothed_rate` and confirm:

       * Smooth curve.
       * Follows long-term trend but doesn’t overreact to single year noise.
       * Current year not treated as artificially low in mid-year snapshots.

4. **Performance:**

   * Number of papers is modest; per-paper 1D Kalman smoothing is O(T) with T ~ 10–30 years, so trivial.
