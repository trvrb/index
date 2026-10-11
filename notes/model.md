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

For paper `i` at age `a` (years since its start year), the latent log citation rate is `x`:

```
x_{i,0} ~ N(m0, v0)
x_{i,a} = x_{i,a-1} + δ_{min(a,K)} + ε,   ε ~ N(0, q)
y_{i,a} ~ Poisson(e_{i,a} · exp(x_{i,a}))
```

- **Exposure.** `e` is the fraction of the year observed. It is 1, except in the year of the scrape.
- **Zeros.** Missing years in Scholar's histogram are true zeros. They enter the likelihood
  directly, with no pseudocount.
- **Start year.** A paper starts at `min(pub_year, first cited year)`. Preprints can be cited
  before publication.
- **Papers without a publication year.** These start at their first cited year, which has at
  least one citation by construction. That first count uses a zero-truncated Poisson likelihood.
- **Shared hyperparameters.** The process variance `q`, the first-year prior `(m0, v0)` and the
  age drift `δ_1..δ_K` are shared across papers.

## Inference

We use the Laplace approximation, implemented in `kalman.poisson_laplace`:

1. **Mode finding.** Each Newton step for the posterior mode of the latent path replaces the
   Poisson observations with Gaussian working observations
   `z = x̂ + score/info`, with variance `1/info`. One Kalman filter plus RTS smoother pass on
   these gives the exact Newton update. The posterior is log-concave, so this converges in about
   6 iterations, with step-halving as a safeguard.
2. **Posterior variance.** At the mode, the smoother's variances `P` are the Laplace posterior
   variances of `x`.
3. **Marginal likelihood:**
   ```
   log p(y) ≈ log L_KF(z) + Σ [log p(y | x̂) − log N(z | x̂, 1/info)]
   ```
   The tests check this against 2D quadrature for a large-count series.

Every paper is processed in one batch: arrays are shaped (papers × ages) and aligned by age.

## Fitting

`model.tune.fit_hyperparameters` maximizes the summed marginal likelihood with Nelder–Mead, then
restarts once. A fit takes about 5 s. Results on the October 2026 scrape (162 papers, no
publication years yet):

| K | log-lik | AIC | q | m0 | v0 | δ |
|---|---|---|---|---|---|---|
| 0 | −3909.7 | 7825.4 | 0.280 | 1.57 | 0.94 | — |
| 1 | −3909.1 | 7826.2 | 0.280 | 1.56 | 0.95 | [0.02] |
| 2 | −3768.4 | 7546.8 | 0.162 | 1.17 | 1.35 | [1.01, −0.07] |
| **3** | **−3763.1** | **7538.2** | 0.158 | 1.15 | 1.38 | **[0.98, 0.08, −0.09]** |
| 4 | −3762.9 | 7539.9 | 0.158 | 1.15 | 1.38 | [0.98, 0.08, −0.12, −0.09] |

K=3 has the lowest AIC. A typical paper's citation rate rises about 2.7× from its first to its
second year, holds steady, then declines about 9% per year.

**What K=3 means.** Once drift is included, the process variance falls from 0.28 to 0.16: much of
the apparent volatility was the predictable life cycle.

**Why the first-year jump is so large.** First years are usually partial. For example, Nextstrain
was published December 2018. Publication month is on Scholar's paper page and could be used as
first-year exposure, but it isn't used yet.

**Overdispersion.** A negative binomial observation model was also tried. Its dispersion
estimate went to 0, so the random walk already absorbs the extra-Poisson variation.

## Forecasts

`model.forecast.simulate` draws each paper's current log rate from `N(x̂_T, P_T)`, jointly across
papers, then:

1. **Finishes the current year:** observed count + `Poisson((1 − e) · λ)`.
2. **Projects H years ahead.** Each step adds the drift for the paper's age in the target year,
   plus noise.
3. **Summarizes:**
   - Per-paper quantiles of the rate are analytic (lognormal).
   - Quantiles of cumulative counts, total citations and h-index come from the draws.
   - The h-index and i10-index add each paper's undated citations (Scholar's total minus the
     dated histogram, about 1.4%). This makes the "to date" values match Scholar's profile, and
     keeps projections from falling below them.

## Backtest

`python -m model.backtest` uses rolling origins 2020–2023:

- **Procedure.** At each origin, refit on data through that year, then predict each paper's
  count 1 and 2 full years ahead. Papers that start after the origin are predicted from the
  population prior.
- **Measures.** Log predictive score per paper, coverage of the 80% interval, absolute error of
  `log1p` of the predictive median, and the ratio of predicted to observed totals for each origin.

Results on the October 2026 scrape, for papers that existed at the origin:

| Model | h | log score | 80% cov | MAE log1p | pred/obs total |
|---|---|---|---|---|---|
| Original pipeline (prototype re-run) | 1 | −3.235 | 0.85 | 0.527 | 0.86 1.16 1.43 1.29 |
| Poisson, K=0 | 1 | −3.136 | 0.90 | 0.474 | 0.91 1.25 1.50 1.33 |
| **Poisson, K=3** | 1 | **−3.066** | 0.84 | **0.469** | 0.99 1.23 1.38 1.16 |
| Original pipeline (prototype re-run) | 2 | −3.315 | 0.89 | 0.607 | 1.12 1.67 1.81 1.48 |
| Poisson, K=0 | 2 | −3.233 | 0.92 | 0.540 | 1.22 1.92 2.02 1.60 |
| **Poisson, K=3** | 2 | **−3.172** | 0.84 | 0.554 | 1.25 1.65 1.60 1.19 |

**Why totals are overpredicted after 2021.** All models overpredict totals at those origins,
because of the sharp post-COVID decline in citations to the large 2020–21 papers. No paper-level
random walk can anticipate it. The K=3 drift cuts the overshoot considerably.

## Possible extensions

- First-year exposure from the publication month.
- A local linear (damped) trend, to give each paper its own momentum on top of the population drift.
- An estimate of Scholar's indexing lag from the scrape snapshots kept in git history.
  - Within 2026, the annualized total rose from 2,297 (Feb) to 2,897 (Oct). That is consistent
    with either about a 10-day indexing lag or real growth.
  - Backfill into the previous year after year-end was small (under 3%).
