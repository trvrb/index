# Citation rate model

This note describes the model in `model/`, which replaced the original log-scale Kalman
smoother described in `kalman.md`, `kalman_tuning.md` and `kalman_forecasts.md`. It also
records why the model was changed.

## Problems with the original model

1. **Zero-citation years were dropped.** Scholar's per-paper histogram leaves out years with
   zero citations. The year grid was built from the histogram's years, so those zeros never
   reached the model. On the October 2026 scrape this was 150 of 1309 paper-years:
   - 28 papers had interior gaps, which the random walk treated as adjacent years.
   - 26 papers ended at their last nonzero year, so their final rate never declined.
2. **The observation model weighted data by itself.** The variance was
   `R_t = φ/(y_t + 0.5) + 0.01`, computed from the observed count, so high draws were trusted
   more than low ones. Observations were `log(y + 0.5)`. The fitted φ ≈ 0.5 was below the
   Poisson value of 1, a sign of misfit.
3. **The prior reused the first observation.** `x0_mean = z[0]` counted it twice.
4. **No paper life cycle.** A driftless random walk forecasts a flat rate with fast-growing
   uncertainty.

## Model

For paper `i` at age `a` (years since its start year), the latent log citation rate is `x`, and
`d` is the paper's slope deviation from the typical trajectory. The deviation carries momentum:

```
x_{i,0} ~ N(m0, v0),   d_{i,0} ~ N(0, r / (1 − ρ²))
d_{i,a} = ρ · d_{i,a-1} + ζ,                        ζ ~ N(0, r)
x_{i,a} = x_{i,a-1} + δ_{min(a,K)} + ρ · d_{i,a-1} + ζ + ε,   ε ~ N(0, q)
y_{i,a} ~ Poisson(e_{i,a} · exp(x_{i,a}))
```

- **Exposure.** `e` is the fraction of the year observed. It is 1, except in the year of the scrape.
- **Zeros.** Missing years in Scholar's histogram are true zeros. They enter the likelihood
  directly, with no pseudocount.
- **Start year.** A paper starts at `min(pub_year, first cited year)`. Preprints can be cited
  before publication.
- **Papers without a publication year.** These start at their first cited year, which has at
  least one citation by construction. That first count uses a zero-truncated Poisson likelihood.
- **Momentum.** A paper rising faster than typical for its age keeps rising faster, and a paper
  falling faster keeps falling. The excess decays by a factor of ρ each year.
- **Special case.** With ρ = 0 and r = 0, the model is a random walk with age-specific drift.
  That was the first version of this model.
- **Shared hyperparameters.** These are shared across papers:
  - the level and slope variances `(q, r)`
  - the first-year prior `(m0, v0)`
  - the age drift `δ_1..δ_K`
  - the persistence ρ, which is fixed (see Fitting)

## Inference

We use the Laplace approximation, implemented in `kalman.poisson_laplace`:

1. **Mode finding.** Each Newton step for the posterior mode of the latent path replaces the
   Poisson observations with Gaussian working observations
   `z = x̂ + score/info`, with variance `1/info`. One Kalman filter plus RTS smoother pass on
   these gives the exact Newton update. The posterior is log-concave, so this converges in about
   6 iterations, with step-halving as a safeguard.
2. **Posterior variance.** At the mode, the smoother's covariances are the Laplace posterior
   covariances of `(x, d)`. Forecasts start from them.
3. **Marginal likelihood:**
   ```
   log p(y) ≈ log L_KF(z) + Σ [log p(y | x̂) − log N(z | x̂, 1/info)]
   ```
   The tests check this against 2D quadrature for a large-count series.

Every paper is processed in one batch: arrays are shaped (papers × ages) and aligned by age.

The step-halving check needs the prior density of a log-rate path, with the slope integrated out.
Running the Kalman filter on the path itself, with zero observation noise, gives this density.

## Fitting

`model.tune.fit_hyperparameters` maximizes the summed marginal likelihood with Nelder–Mead, then
restarts once. Each Newton solve starts from the previous evaluation's mode. A fit takes about
15 s.

### Drift by age

Results on the October 2026 scrape (162 papers, no publication years yet), without momentum:

| K | log-lik | AIC | q | m0 | v0 | δ |
|---|---|---|---|---|---|---|
| 0 | −3909.7 | 7825.4 | 0.280 | 1.57 | 0.94 | — |
| 1 | −3909.1 | 7826.2 | 0.280 | 1.56 | 0.95 | [0.02] |
| 2 | −3768.4 | 7546.8 | 0.162 | 1.17 | 1.35 | [1.01, −0.07] |
| **3** | **−3763.1** | **7538.2** | 0.158 | 1.15 | 1.38 | **[0.98, 0.08, −0.09]** |
| 4 | −3762.9 | 7539.9 | 0.158 | 1.15 | 1.38 | [0.98, 0.08, −0.12, −0.09] |

K=3 has the lowest AIC. A typical paper's citation rate rises about 2.7× from its first to its
second year, holds steady, then declines about 9–10% per year.

**What K=3 means.** Once drift is included, the process variance falls from 0.28 to 0.16: much of
the apparent volatility was the predictable life cycle.

### Momentum

Without momentum, every mature paper got the same forecast: its current level falling about 9%
a year, whatever its recent trend. The table shows the fit with K=3 and ρ held at each value,
plus the 1-year-ahead backtest score (2020–2024 origins; higher is better). The last two columns
are forecast medians for 2026 → 2029.

| ρ | log-lik | 1-yr log score | q | r | Global circulation | Nextstrain |
|---|---|---|---|---|---|---|
| 0 | −3763.1 | −3.018 | (0.158 total) | | 123 → 112 → 102 → 93 | 493 → 449 → 410 → 373 |
| 0.3 | −3750.8 | −3.002 | 0.000 | 0.117 | 123 → 130 → 124 → 114 | 492 → 478 → 442 → 403 |
| **0.5** | −3749.3 | −3.004 | 0.029 | 0.071 | **123 → 137 → 137 → 130** | **492 → 482 → 453 → 417** |
| 0.7 | −3748.4 | −3.002 | 0.064 | 0.032 | 123 → 136 → 141 → 140 | 492 → 472 → 443 → 410 |
| 0.9 | −3746.4 | −3.003 | 0.088 | 0.009 | 123 → 132 → 140 → 145 | 493 → 494 → 488 → 477 |
| 0.989 (free) | −3745.2 | — | 0.101 | 0.001 | 123 → 130 → 138 → 145 | 495 → 564 → 640 → 725 |

**Reading the table:**
- **Momentum is supported.** Any ρ > 0 improves the log-likelihood by 12–17 and the
  out-of-sample score slightly but consistently. Most of the gain is already there at ρ = 0.3.
- **The data can't pin down ρ.** The likelihood is nearly flat above 0.3.
- **Why not fit ρ freely.** The free fit runs to ρ ≈ 1 with almost no slope variance. That
  gives each paper a permanent growth rate: it extrapolates surges (Nextstrain to 725/yr) and
  overpredicts totals in backtests.
- **Choice: ρ = 0.5,** so a deviation from the typical trajectory halves each year.
  `--persistence` changes it.

**Why the first-year jump is so large.** First years are usually partial. For example, Nextstrain
was published December 2018. Publication month is on Scholar's paper page and could be used as
first-year exposure, but it isn't used yet.

**Overdispersion.** A negative binomial observation model was also tried. Its dispersion
estimate went to 0, so the random walk already absorbs the extra-Poisson variation.

## Forecasts

`model.forecast.simulate` draws each paper's current log rate and slope deviation `(x_T, d_T)`
from their joint Laplace posterior, jointly across papers, then:

1. **Finishes the current year:** observed count + `Poisson((1 − e) · λ)`.
2. **Projects H years ahead.** Each step adds the drift for the paper's age in the target year,
   the paper's decaying momentum `ρ · d`, and noise.
3. **Summarizes:**
   - Per-paper quantiles of the rate are analytic (lognormal).
   - Quantiles of cumulative counts, total citations and h-index come from the draws.
   - The h-index and i10-index add each paper's undated citations (Scholar's total minus the
     dated histogram, about 1.4%). This makes the "to date" values match Scholar's profile, and
     keeps projections from falling below them.

## Backtest

`python -m model.backtest` uses rolling origins (2020–2024 by default):

- **Procedure.** At each origin, refit on data through that year, then predict each paper's
  count 1 and 2 full years ahead. Papers that start after the origin are predicted from the
  population prior.
- **Measures.** Log predictive score per paper, coverage of the 80% interval, absolute error of
  `log1p` of the predictive median, and the ratio of predicted to observed totals for each origin.

Results on the October 2026 scrape, for papers that existed at the origin. The first comparison
used origins 2020–2023, before momentum was added:

| Model | h | log score | 80% cov | MAE log1p | pred/obs total |
|---|---|---|---|---|---|
| Original pipeline (prototype re-run) | 1 | −3.235 | 0.85 | 0.527 | 0.86 1.16 1.43 1.29 |
| Poisson, K=0 | 1 | −3.136 | 0.90 | 0.474 | 0.91 1.25 1.50 1.33 |
| **Poisson, K=3** | 1 | **−3.066** | 0.84 | **0.469** | 0.99 1.23 1.38 1.16 |
| Original pipeline (prototype re-run) | 2 | −3.315 | 0.89 | 0.607 | 1.12 1.67 1.81 1.48 |
| Poisson, K=0 | 2 | −3.233 | 0.92 | 0.540 | 1.22 1.92 2.02 1.60 |
| **Poisson, K=3** | 2 | **−3.172** | 0.84 | 0.554 | 1.25 1.65 1.60 1.19 |

Momentum (K=3, origins 2020–2024):

| ρ | h | log score | 80% cov | MAE log1p | pred/obs total |
|---|---|---|---|---|---|
| 0 | 1 | −3.018 | 0.85 | 0.462 | 0.99 1.23 1.38 1.16 1.04 |
| **0.5** | 1 | **−3.004** | 0.86 | **0.460** | 1.08 1.33 1.39 1.14 1.00 |
| 0 | 2 | −3.172 | 0.84 | 0.555 | 1.25 1.65 1.60 1.19 |
| **0.5** | 2 | **−3.164** | 0.85 | **0.544** | 1.46 1.91 1.66 1.17 |

Papers published after the origin score the same with or without momentum, because they have
no history to carry forward.

**Why totals are overpredicted after 2021.** All models overpredict totals at those origins,
because of the sharp post-COVID decline in citations to the large 2020–21 papers. No paper-level
random walk can anticipate it. The K=3 drift cuts the overshoot considerably. Momentum adds
some back for the origins right after the surge, since it carries the surge forward a little. By
the 2024 origin, totals are on target with or without momentum.

## Possible extensions

- First-year exposure from the publication month.
- An estimate of Scholar's indexing lag from the scrape snapshots kept in git history. This
  matters more with momentum, which carries a partial-year bump forward.
  - Within 2026, the annualized total rose from 2,297 (Feb) to 2,897 (Oct). That is consistent
    with either about a 10-day indexing lag or real growth.
  - Backfill into the previous year after year-end was small (under 3%).
