# index

A tool for tracking and visualizing Google Scholar citation data over time.

## Overview

This project has three components:

1. **Ingest** (`ingest/`) - Scrapes citation data from Google Scholar
2. **Model** (`model/`) - Estimates citation rates and forecasts with a Poisson state-space model
3. **Visualization** (root) - D3.js interactive charts, deployed via GitHub Pages

## Installation

```bash
pip install -r requirements.txt
```

## Usage

### 1. Scrape citation data from Google Scholar

Configure your Google Scholar user ID in `config.yaml`:

```yaml
user_id: RIi-1pAAAAAJ
request_delay: 2
```

Run the scraper:

```bash
python -m ingest            # update papers whose citation counts changed
python -m ingest --refresh  # re-fetch every paper
```

Output: `results/citations.json` with each paper's publication year, total citations and citations per year, plus the profile's summary stats.

Scholar rate-limits after about 100 requests, so the scraper avoids requests it doesn't need:

- **Every run fetches the paper list** (about 9 requests). The list shows each paper's "Cited by" count.
- **Detail pages are fetched only when needed:** for new papers and papers whose count changed. Unchanged papers are marked current as of now. Uncited papers need no request.
- **Order:** changed papers are fetched largest change first.
- **Interruptions:** if Scholar rate-limits you, progress is saved and existing data is kept. Re-run `python -m ingest` to continue.
- **`--refresh`:** Scholar occasionally moves a citation between years without changing a paper's total, which change detection can't see. `--refresh` re-fetches every paper and is resumable the same way. The scraper suggests running it when papers haven't been fetched in 180 days.
- **Model warnings:** `python -m model.rates` warns when stored counts are behind Scholar's.

**Note:** The scraper uses browser cookies for authentication. You must be logged into Google in Chrome, Firefox, or Safari.

### 2. Estimate citation rates and forecasts

```bash
python -m model.rates
```

This reads `results/citations.json`, fits the model hyperparameters by maximum marginal likelihood (a few seconds), and writes `data/citation_rates.json`, which the visualization reads. Options:

- `--forecast-lead YEARS`: forecast through the last year-end within this many years of the scrape date (default 1.5). Before July that's the end of the current year; from July on, the end of next year.
- `--params FILE`: use fixed hyperparameters from `model.tune` instead of fitting
- `--drift-ages K`: number of age-specific drift parameters (default 3)
- `--persistence RHO`: fraction of a paper's momentum kept each year (default 0.5; 0 turns momentum off)

### 3. Diagnostics (optional)

```bash
python -m model.tune       # fit and save hyperparameters to results/tuned_params.json
python -m model.backtest   # rolling-origin backtest, with and without momentum
pytest                     # unit tests
```

### 4. View the visualization

The visualization is deployed via GitHub Pages at: https://trvrb.github.io/index

For local development, run a server from the repository root:

```bash
python -m http.server 8000
```

Then open http://localhost:8000 in your browser.

The visualization includes:

- **Summary stats**: Total citations, h-index, i10-index, and citations this year with a year-end projection
- **H-index over time**: The observed h-index by year, with a forecast fan
- **All paper citations over time**: Stacked area chart of every paper's smoothed citation rate, colored by publication year
- **All paper citations at a specific year**: Treemap of each paper's share of citations
- **Specific paper citations over time**: One paper's observed citations, smoothed rate with an 80% interval, and forecast

The Yearly/Accumulated toggle switches between citations per year and cumulative citations. Click any paper in the stacked chart or treemap to view it in the per-paper plot. The shaded region marks the partial current year and later years, which are projections.

## Project Structure

```
index/
├── index.html          # Visualization entry point
├── app.js              # D3.js visualization code
├── styles.css          # Styling
├── data/
│   └── citation_rates.json  # Model output for GitHub Pages
├── results/            # Local working outputs (gitignored)
├── ingest/             # Google Scholar scraper
├── model/
│   ├── data.py         # Zero-filled yearly series and exposure
│   ├── kalman.py       # Batched Kalman smoother and Poisson Laplace approximation
│   ├── tune.py         # Hyperparameter fitting
│   ├── forecast.py     # Monte Carlo forecasts of citations and h-index
│   ├── backtest.py     # Rolling-origin forecast evaluation
│   └── rates.py        # CLI producing data/citation_rates.json
├── notes/              # Design notes (model.md describes the current model)
└── tests/
```

## Data Formats

### citations.json

Raw scraped data:

```json
{
  "user_id": "RIi-1pAAAAAJ",
  "scraped_at": "2026-10-11T05:43:05+00:00",
  "profile": { "citations": 24945, "h_index": 66, "i10_index": 135 },
  "papers": [
    {
      "title": "Paper Title",
      "citation_id": "RIi-1pAAAAAJ:HoB7MX3m0LUC",
      "pub_year": 2018,
      "total_citations": 77,
      "listed_citations": 77,
      "citations_by_year": { "2018": 10, "2019": 25, "2021": 42 },
      "fetched_at": "2026-09-02T18:10:44+00:00",
      "scraped_at": "2026-10-11T05:43:05+00:00"
    }
  ]
}
```

Scholar omits years with zero citations from `citations_by_year`; the model treats them as zeros.

- `listed_citations` is the paper's count on the profile list when its detail page was last fetched.
- `fetched_at` is when the detail page was last fetched.
- `scraped_at` is when the counts were last confirmed current. Exposure for the current year is computed from it.
- Papers with a change on Scholar that hasn't been fetched yet carry `"stale": true`.

### citation_rates.json

Model output (abbreviated):

```json
{
  "current_year": 2026,
  "exposure_fraction_current": 0.776,
  "model": { "type": "poisson_state_space", "process_var": 0.029, "slope_var": 0.071,
             "persistence": 0.5, "init_mean": 1.14, "init_var": 1.38,
             "drift": [1.02, 0.08, -0.10], "interval": 0.8 },
  "summary": { "years": [...], "h_index": [...], "citations": [...],
               "h_index_to_date": 66, "i10_index_to_date": 135, "citations_to_date": 24936 },
  "forecast": { "years": [2026, 2027],
                "h_index_q10": [...], "h_index_q50": [...], "h_index_q90": [...],
                "citations_q50": [...], "cumulative_q50": [...] },
  "papers": [
    {
      "title": "Paper Title",
      "pub_year": 2018,
      "total_citations": 100,
      "years": [2018, 2019, 2020, 2021],
      "observed_citations": [10, 25, 0, 42],
      "exposure_fraction": [1.0, 1.0, 1.0, 1.0],
      "empirical_rate": [10.0, 25.0, 0.0, 42.0],
      "smoothed_rate": [11.2, 20.5, 22.3, 35.0],
      "smoothed_rate_mean": [12.0, 21.4, 23.6, 36.8],
      "smoothed_rate_lower": [7.1, 14.8, 15.2, 26.0],
      "smoothed_rate_upper": [17.6, 28.4, 32.7, 47.1],
      "forecast": { "rate_mean": [...], "rate_q10": [...], "rate_q50": [...], "rate_q90": [...],
                    "cumulative_q10": [...], "cumulative_q50": [...], "cumulative_q90": [...] }
    }
  ]
}
```

- `smoothed_rate` is the posterior median rate.
- `smoothed_rate_mean` is the posterior mean, used when stacking papers.
- `smoothed_rate_lower` and `smoothed_rate_upper` bound the 80% interval.
- Forecast arrays line up with `forecast.years`. The first entry is the year-end projection for the partial current year.
- Summary and forecast h-index values count undated citations, so they match Scholar's profile. Historical values use dated citations only.

## Model

Each paper's log citation rate follows a typical life-cycle trajectory for its age, plus its own momentum. A paper rising faster than typical keeps rising faster, and the excess fades each year. Yearly counts are Poisson, scaled by the fraction of the year observed:

```
x_0 ~ N(m0, v0),   d_0 ~ N(0, r / (1 − ρ²))
d_a = ρ · d_{a-1} + ζ,                            ζ ~ N(0, r)
x_a = x_{a-1} + δ_{min(a,K)} + ρ · d_{a-1} + ζ + ε,   ε ~ N(0, q)
y_a ~ Poisson(e_a · exp(x_a))
```

- **Inference:** the Laplace approximation. Its Newton iterations are Kalman filter and RTS smoother passes on Gaussian working observations.
- **Hyperparameters:** `q`, `r`, `m0`, `v0` and `δ` are shared across papers and fit by maximizing the approximate marginal likelihood.
- **Momentum:** ρ is fixed at 0.5, so a paper's deviation from the typical trajectory halves each year. The data support momentum but can't pin down how persistent it is.
- **Drift:** with K=3, a typical paper's rate rises about 2.8× into its second year, holds steady, then declines about 10% per year.
- **Forecasts:** these simulate all papers jointly, which gives intervals for total citations and h-index. They run through the last year-end within 1.5 years of the scrape.

See `notes/model.md` for details, the model comparison, and backtest results.
