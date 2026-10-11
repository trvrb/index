"""Data preparation shared by model.rates, model.tune and model.backtest.

Turns scraped Google Scholar citation histograms into zero-filled yearly
series with exposure, and packs them into age-aligned arrays for the batched
Kalman filter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import numpy as np


def parse_scraped_at(scraped_at_str: str) -> datetime:
    """Parse scraped_at timestamp to timezone-aware datetime."""
    if scraped_at_str.endswith("Z"):
        scraped_at_str = scraped_at_str[:-1] + "+00:00"
    dt = datetime.fromisoformat(scraped_at_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def compute_exposure_fraction(scraped_at: datetime) -> float:
    """Compute fraction of the scrape year that has been observed.

    Returns:
        Fraction between 0 and 1 representing how much of the year has passed.
    """
    tz = scraped_at.tzinfo or timezone.utc
    year_start = datetime(scraped_at.year, 1, 1, tzinfo=tz)
    next_year_start = datetime(scraped_at.year + 1, 1, 1, tzinfo=tz)

    total_seconds = (next_year_start - year_start).total_seconds()
    elapsed_seconds = (scraped_at - year_start).total_seconds()
    fraction = elapsed_seconds / total_seconds

    # Sanity check
    if not (0.0 < fraction <= 1.0):
        return 1.0
    return fraction


@dataclass
class Series:
    """A paper's zero-filled yearly citation series."""

    title: str
    years: list[int]
    counts: np.ndarray
    exposure: np.ndarray
    pub_year: Optional[int]
    total_citations: Optional[int]
    # True when the series starts at the first cited year (no publication year
    # known), so the first count is >= 1 by construction and is modeled as a
    # zero-truncated observation.
    first_obs_truncated: bool

    @property
    def dated_citations(self) -> int:
        return int(self.counts.sum())

    @property
    def undated_citations(self) -> int:
        """Citations Scholar counts in total but doesn't assign to a year."""
        if self.total_citations is None:
            return 0
        return max(0, int(self.total_citations) - self.dated_citations)


def load_citations(path: str) -> dict[str, Any]:
    """Load raw scraped citations JSON."""
    with open(path) as f:
        return json.load(f)


def _valid_year(value: Any) -> Optional[int]:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if 1900 <= year <= 2100 else None


def build_series(
    paper: dict[str, Any],
    scraped_at: datetime,
    end_year: Optional[int] = None,
) -> Optional[Series]:
    """Build a zero-filled yearly series for one paper.

    The year grid runs from the paper's start year through `end_year`
    (default: the scrape year). Scholar omits years with zero citations, so
    every missing year in the grid is a true zero.

    The start year is min(pub_year, first cited year) when the publication
    year is known (preprints can be cited before publication). Otherwise it's
    the first cited year, and that first count is flagged as truncated.

    Args:
        paper: Paper dict with title, citations_by_year and optionally
            pub_year, total_citations and scraped_at.
        scraped_at: When the data was scraped (fallback for papers without
            their own scraped_at).
        end_year: Last year of the grid. Years before the scrape year are
            treated as fully observed, which is how backtests truncate data.

    Returns:
        Series, or None if the paper has nothing to model within the grid.
    """
    if paper.get("citations_by_year") is None:
        return None  # not scraped yet (interrupted scrape)

    paper_scraped_at = scraped_at
    if paper.get("scraped_at"):
        paper_scraped_at = parse_scraped_at(paper["scraped_at"])
    scrape_year = scraped_at.year
    if end_year is None:
        end_year = scrape_year

    citations = {
        int(year): int(count)
        for year, count in (paper.get("citations_by_year") or {}).items()
        if int(year) <= end_year
    }
    cited_years = [year for year, count in citations.items() if count > 0]
    pub_year = _valid_year(paper.get("pub_year"))

    if pub_year is not None and pub_year <= end_year:
        start = min([pub_year] + cited_years)
        truncated = False
    elif cited_years:
        start = min(cited_years)
        truncated = True
    else:
        return None

    years = list(range(start, end_year + 1))
    counts = np.array([citations.get(year, 0) for year in years], dtype=float)

    exposure = np.ones_like(counts)
    if end_year == scrape_year:
        if paper_scraped_at.year == scrape_year:
            exposure[-1] = compute_exposure_fraction(paper_scraped_at)
        else:
            exposure[-1] = compute_exposure_fraction(scraped_at)

    return Series(
        title=paper["title"],
        years=years,
        counts=counts,
        exposure=exposure,
        pub_year=pub_year,
        total_citations=paper.get("total_citations"),
        first_obs_truncated=truncated,
    )


def to_arrays(
    series: list[Series],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Pack series into age-aligned arrays for the batched Kalman filter.

    Column a holds each paper's a-th year since its start year. Rows are
    padded at the end; padded cells have mask False.

    Returns:
        Tuple of (Y counts, E exposure, mask, trunc), each shaped
        (n_papers, n_ages). trunc marks zero-truncated observations.
    """
    n_papers = len(series)
    n_ages = max(len(s.years) for s in series)

    Y = np.zeros((n_papers, n_ages))
    E = np.ones((n_papers, n_ages))
    mask = np.zeros((n_papers, n_ages), dtype=bool)
    trunc = np.zeros((n_papers, n_ages), dtype=bool)

    for i, s in enumerate(series):
        n = len(s.years)
        Y[i, :n] = s.counts
        E[i, :n] = s.exposure
        mask[i, :n] = True
        trunc[i, 0] = s.first_obs_truncated

    return Y, E, mask, trunc


def h_index(citations: np.ndarray) -> np.ndarray:
    """Compute h-index along the last axis of an array of citation counts."""
    ranked = -np.sort(-np.asarray(citations, dtype=float), axis=-1)
    ranks = np.arange(1, ranked.shape[-1] + 1)
    return (ranked >= ranks).sum(axis=-1)


def i10_index(citations: np.ndarray) -> np.ndarray:
    """Compute i10-index (papers with at least 10 citations) along the last axis."""
    return (np.asarray(citations) >= 10).sum(axis=-1)
