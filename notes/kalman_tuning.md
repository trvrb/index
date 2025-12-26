
## 1. Make the observation model more realistic first

Right now you’re modeling

> `z_t = log(empirical_rate_t + min_count)`
> with
> `z_t = x_t + η_t`,  η_t ~ N(0, R) (constant R = `obs_var`)

But your counts are, in practice, **Poisson-ish**:

* `y_t ~ Poisson(e_t * λ_t)`
* `r_t = y_t / e_t` ≈ annualized rate
* For Poisson, `Var(y_t) = e_t * λ_t`.
* Using the delta method, `Var(log y_t)` ≈ `1 / (e_t * λ_t)` for large λ.

So on the log scale, the observation noise **should depend on the rate**. That suggests:

```text
base_R_t ≈ 1 / (empirical_rate_t + min_count)
```

Then you let:

```text
R_t = φ * base_R_t + σ_min²
```

* `φ ≥ 1` is a **global overdispersion factor** (Poisson would be φ ≈ 1; overdispersed data ⇒ φ > 1).
* `σ_min²` is a small floor to stop R_t getting absurdly tiny at very high counts (e.g. σ_min² ~ 0.01).

This makes high-citation years (e.g. 2020–2022 for the Nextstrain paper) **more precisely measured** than tiny-count years, which is what you want. It also largely removes the need to pick a single magic `--obs-var`.

Implementation-wise, it just means your Kalman filter uses a **time-varying** observation variance `R_t` instead of a scalar `R`.

---

## 2. Estimate `process_var` (and φ) by maximizing marginal likelihood

Given the linear-Gaussian state-space model on log-rates:

* State: `x_t` (log λ_t), random walk with variance `q` (`process_var`).
* Observation: `z_t` with variance `R_t(φ)` as above.

The Kalman filter already gives you the **log marginal likelihood**:

[
\log p(z_{1:T} \mid q, \phi)
= -\tfrac12 \sum_{t=1}^T \left[
\log 2\pi
+ \log S_t
+ v_t^2 / S_t
\right]
]

where at each step of the filter:

* `v_t = z_t - H x_pred_t` is the one-step-ahead prediction error (with H = 1).
* `S_t = H P_pred_t Hᵀ + R_t(φ)` is its variance.

So a **principled tuning strategy** is:

### Global hyperparameters across all papers

1. For each paper `i`, compute its `z_t^i` and `base_R_t^i`.

2. Pick a grid or small 2D search domain for `q` and `φ`:

   * e.g. `q` in `exp(np.linspace(-3, 1, 40))` (≈ 0.05 to ~2.7).
   * `φ` in `exp(np.linspace(-1, 2, 40))` (≈ 0.37 to ~7.4).

3. For each `(q, φ)` pair:

   * For each paper `i`, run the Kalman filter with:

     * process variance `Q = q`
     * observation variance trajectory `R_t^i = φ * base_R_t^i + σ_min²`
   * Sum the log-likelihoods over papers:

     ```text
     L(q, φ) = Σ_i log p(z^i | q, φ)
     ```

4. Choose `(q*, φ*)` that **maximizes** `L(q, φ)` (or equivalently minimizes `-L`).

This gives you a **single pair of hyperparameters** supported by the entire corpus. Intuitively:

* `q*` = how volatile log citation rates are, on average, year-to-year.
* `φ*` = how noisy counts are relative to a pure Poisson idealization.

You can then use those as **default** `--process-var` and `--obs-overdispersion` in your CLI.

---

## 3. Back-of-the-envelope sanity check for q

Even before ML, you can approximate a reasonable scale for `q` from the **log differences**.

For Nextstrain’s empirical rates:

* 2018 → 2019: 20 → 60 → Δlog ≈ log(3) ≈ 1.10
* 2019 → 2020: 60 → 445 → Δlog ≈ log(7.42) ≈ 2.00
* 2020 → 2021: 445 → 860 → Δlog ≈ log(1.93) ≈ 0.66

If your model is:

* `x_t = x_{t-1} + ε_t`, ε_t ~ N(0, q)
* `z_t = x_t + η_t`, η_t ~ N(0, r_t)

Then approximately:

[
\Delta z_t \approx \Delta x_t + (\eta_t - \eta_{t-1})
]

and

[
\mathrm{Var}(\Delta z_t) \approx 2q + 2 \bar{r}
]

where `\bar{r}` is some typical observation variance. So if you look at the **sample variance** of Δz_t across all t and all papers, you get a rough constraint:

[
q \lesssim \tfrac12 \mathrm{Var}(\Delta z_t)
]

In a series where Δlog rates often are of size ~1–2, you’d expect `q` on the order of **0.5–1.0**, not 0.15. The ML procedure above will formalize that intuition.

---

## 4. What this would mean for your CLI / code

Concretely, you could evolve your tooling like this:

1. **Change the Kalman code** to accept:

   * `process_var` `q`
   * a global scalar `obs_overdispersion` φ and compute `R_t` from counts

2. Add an **offline hyperparameter tuner** (separate script or subcommand), e.g.:

   ```bash
   python -m model.tune \
     --input citations.json \
     --output tuned_hyperparams.json
   ```

   that runs the marginal-likelihood search and spits out `q*` and `φ*`.

3. Then your analysis CLI uses those as defaults:

   ```bash
   python -m index.rates \
     --input citations.json \
     --output citation_rates.json \
     --process-var 0.9 \
     --obs-overdispersion 1.7
   ```

   where the numbers come from the tuner.

You can always override them, but you now have a **generative story** for how you got them.
