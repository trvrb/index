# index

A tool for tracking and visualizing Google Scholar citation data over time.

## Overview

This project has three components:

1. **Ingest** (`ingest/`) - Scrapes citation data from Google Scholar
2. **Model** (`model/`) - Smooths citation rates using a Kalman filter
3. **Visualization** - D3.js charts for GitHub Pages (planned)

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 1. Scrape citation data from Google Scholar

Configure your Google Scholar user ID in `config.yaml`:

```yaml
user_id: RIi-1pAAAAAJ
request_delay: 5
```

Run the scraper:

```bash
python -m ingest
```

Output: `results/citations.json` with raw citation counts per paper per year.

**Note:** The scraper uses browser cookies for authentication. You must be logged into Google in Chrome, Firefox, or Safari.

### 2. Tune Kalman filter hyperparameters (optional)

Find optimal smoothing parameters for your data:

```bash
python -m model.tune \
  --input results/citations.json \
  --output results/tuned_hyperparams.json \
  --n-grid 50
```

This performs a grid search over process variance and overdispersion, maximizing marginal likelihood across all papers.

### 3. Produce smoothed citation rates

```bash
python -m model.rates \
  --input results/citations.json \
  --output results/citation_rates.json
```

Output: `results/citation_rates.json` with observed counts, empirical rates, and Kalman-smoothed rates with uncertainty.

Default parameters (`--process-var 0.25 --obs-overdispersion 0.56`) were tuned from empirical data.

## Data Formats

### citations.json

Raw scraped data:

```json
{
  "user_id": "RIi-1pAAAAAJ",
  "scraped_at": "2025-12-25T12:00:00+00:00",
  "papers": [
    {
      "title": "Paper Title",
      "total_citations": 100,
      "citations_by_year": { "2020": 10, "2021": 25, "2022": 42 }
    }
  ]
}
```

### citation_rates.json

Smoothed rates:

```json
{
  "user_id": "RIi-1pAAAAAJ",
  "model": { "type": "kalman", "process_var": 0.25, "obs_overdispersion": 0.56 },
  "papers": [
    {
      "title": "Paper Title",
      "years": [2020, 2021, 2022],
      "observed_citations": [10, 25, 42],
      "empirical_rate": [10.0, 25.0, 42.0],
      "smoothed_rate": [12.3, 23.1, 38.5],
      "smoothed_rate_std": [3.2, 4.1, 5.0]
    }
  ]
}
```

## Kalman Filter Model

The smoothing model treats each paper's citation history as a noisy observation of an underlying citation rate that evolves over time.

### State-space formulation

We model the **log citation rate** as a random walk:

```
x_t = x_{t-1} + ε_t,  where ε_t ~ N(0, q)
```

The observed log-counts are noisy measurements of this latent rate:

```
z_t = x_t + η_t,  where η_t ~ N(0, R_t)
```

### Time-varying observation variance

Rather than assuming constant observation noise, we use a Poisson-inspired model where high-count years are measured more precisely:

```
R_t = φ / (rate_t + 0.5) + σ²_min
```

Here φ is an overdispersion factor (φ > 1 indicates more variance than pure Poisson).

### Smoothing

We apply the standard Kalman filter (forward pass) followed by the Rauch-Tung-Striebel smoother (backward pass) to obtain smoothed estimates of the log-rate at each year. Exponentiating gives the smoothed citation rate.

### Hyperparameter tuning

The two key parameters are:

- **Process variance (q)**: Controls how much the underlying rate can change year-to-year. Higher values allow more volatility.
- **Overdispersion (φ)**: Scales the observation noise. Higher values down-weight the observations relative to the prior.

These are tuned by maximizing the marginal likelihood p(observations | q, φ) summed across all papers.
