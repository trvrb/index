from datetime import datetime, timezone

import numpy as np
import pytest

from model.data import (
    build_series,
    compute_exposure_fraction,
    h_index,
    i10_index,
    to_arrays,
)

SCRAPED_AT = datetime(2024, 7, 2, tzinfo=timezone.utc)  # day 183 of 366


def test_exposure_fraction():
    assert compute_exposure_fraction(SCRAPED_AT) == pytest.approx(0.5)
    assert compute_exposure_fraction(datetime(2025, 1, 1, tzinfo=timezone.utc)) == 1.0


def test_zero_fills_interior_and_trailing_years():
    paper = {"title": "A", "citations_by_year": {"2018": 3, "2020": 5, "2022": 1}}
    s = build_series(paper, SCRAPED_AT)
    assert s.years == list(range(2018, 2025))
    assert s.counts.tolist() == [3, 0, 5, 0, 1, 0, 0]
    assert s.exposure[:-1].tolist() == [1.0] * 6
    assert s.exposure[-1] == pytest.approx(0.5)
    assert s.first_obs_truncated


def test_pub_year_sets_start():
    paper = {"title": "A", "pub_year": 2016, "citations_by_year": {"2018": 3}}
    s = build_series(paper, SCRAPED_AT)
    assert s.years[0] == 2016
    assert s.counts[:3].tolist() == [0, 0, 3]
    assert not s.first_obs_truncated


def test_citations_before_pub_year():
    paper = {"title": "Preprint", "pub_year": 2021, "citations_by_year": {"2019": 2, "2021": 4}}
    s = build_series(paper, SCRAPED_AT)
    assert s.years[0] == 2019
    assert not s.first_obs_truncated


def test_uncited_papers():
    with_year = build_series({"title": "A", "pub_year": 2023, "citations_by_year": {}}, SCRAPED_AT)
    assert with_year.years == [2023, 2024]
    assert with_year.counts.tolist() == [0, 0]
    assert build_series({"title": "B", "citations_by_year": {}}, SCRAPED_AT) is None


def test_unscraped_paper_is_skipped():
    paper = {"title": "A", "pub_year": 2020, "total_citations": None, "citations_by_year": None}
    assert build_series(paper, SCRAPED_AT) is None


def test_end_year_truncates_and_uses_full_exposure():
    paper = {"title": "A", "citations_by_year": {"2018": 3, "2020": 5, "2023": 1}}
    s = build_series(paper, SCRAPED_AT, end_year=2021)
    assert s.years == [2018, 2019, 2020, 2021]
    assert s.exposure.tolist() == [1.0] * 4
    assert build_series({"title": "B", "citations_by_year": {"2023": 1}}, SCRAPED_AT, end_year=2021) is None


def test_per_paper_scraped_at():
    paper = {
        "title": "A",
        "citations_by_year": {"2024": 1},
        "scraped_at": "2024-10-01T00:00:00+00:00",
    }
    s = build_series(paper, SCRAPED_AT)
    assert s.exposure[-1] == pytest.approx(274 / 366)


def test_undated_citations():
    paper = {"title": "A", "total_citations": 12, "citations_by_year": {"2020": 4, "2021": 5}}
    assert build_series(paper, SCRAPED_AT).undated_citations == 3


def test_to_arrays_aligns_by_age():
    a = build_series({"title": "A", "citations_by_year": {"2022": 1}}, SCRAPED_AT)
    b = build_series({"title": "B", "pub_year": 2020, "citations_by_year": {"2021": 2}}, SCRAPED_AT)
    Y, E, mask, trunc = to_arrays([a, b])
    assert Y.shape == (2, 5)
    assert mask.sum(axis=1).tolist() == [3, 5]
    assert Y[1, :2].tolist() == [0, 2]
    assert E[0, 2] == pytest.approx(0.5)
    assert trunc[:, 0].tolist() == [True, False]
    assert trunc[:, 1:].sum() == 0


@pytest.mark.parametrize(
    "citations, expected",
    [([10, 8, 5, 4, 3], 4), ([25, 8, 5, 3, 3], 3), ([0, 0], 0), ([100], 1), ([3, 3, 3], 3)],
)
def test_h_index(citations, expected):
    assert h_index(np.array(citations)) == expected


def test_indices_along_last_axis():
    draws = np.array([[10, 8, 5, 4, 3], [25, 9, 10, 3, 3]])
    assert h_index(draws).tolist() == [4, 3]
    assert i10_index(draws).tolist() == [1, 2]
