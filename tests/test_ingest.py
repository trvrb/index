import json

import pytest

import ingest.scholar as scholar
from ingest.output import merge_paper_list, reset_citations, update_paper_progress
from ingest.scholar import Paper, parse_year

PROFILE_PAGE = """
<table id="gsc_rsb_st">
  <tr><th></th><th class="gsc_rsb_sth">All</th><th class="gsc_rsb_sth">Since 2021</th></tr>
  <tr><td>Citations</td><td class="gsc_rsb_std">500</td><td class="gsc_rsb_std">300</td></tr>
  <tr><td>h-index</td><td class="gsc_rsb_std">12</td><td class="gsc_rsb_std">9</td></tr>
  <tr><td>i10-index</td><td class="gsc_rsb_std">15</td><td class="gsc_rsb_std">11</td></tr>
</table>
<table>
  <tr class="gsc_a_tr">
    <td class="gsc_a_t"><a class="gsc_a_at" href="/citations?view_op=view_citation&amp;citation_for_view=U:abc">Paper A</a></td>
    <td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl">2018</span></td>
  </tr>
  <tr class="gsc_a_tr">
    <td class="gsc_a_t"><a class="gsc_a_at" href="/citations?view_op=view_citation&amp;citation_for_view=U:def">Paper B</a></td>
    <td class="gsc_a_y"><span class="gsc_a_h gsc_a_hc gs_ibl"></span></td>
  </tr>
</table>
"""

PAPER_PAGE = """
<div id="gsc_oci_title">Paper A</div>
<div id="gsc_oci_table">
  <div class="gs_scl"><div class="gsc_oci_field">Publication date</div><div class="gsc_oci_value">2018/12/1</div></div>
  <div class="gs_scl"><div class="gsc_oci_field">Total citations</div><div class="gsc_oci_value"><a>Cited by 30</a></div></div>
</div>
<div id="gsc_oci_graph_bars">
  <a href="/scholar?as_ylo=2019&amp;as_yhi=2019"><span class="gsc_oci_g_al">10</span></a>
  <a href="/scholar?as_ylo=2021&amp;as_yhi=2021"><span class="gsc_oci_g_al">18</span></a>
</div>
"""


class FakeResponse:
    def __init__(self, text):
        self.text = text


@pytest.fixture
def fake_scholar(monkeypatch):
    def fetch(url, **kwargs):
        if "view_citation" in url:
            return FakeResponse(PAPER_PAGE)
        return FakeResponse(PROFILE_PAGE if "cstart=0&" in url else "")

    monkeypatch.setattr(scholar, "fetch_with_retry", fetch)
    monkeypatch.setattr(scholar.time, "sleep", lambda s: None)


def test_parse_year():
    assert parse_year("2018/12/1") == 2018
    assert parse_year("2020") == 2020
    assert parse_year("") is None


def test_fetch_paper_list(fake_scholar):
    papers, profile = scholar.fetch_paper_list("U", 0)
    assert papers == [
        {"title": "Paper A", "citation_id": "U:abc", "pub_year": 2018},
        {"title": "Paper B", "citation_id": "U:def", "pub_year": None},
    ]
    assert profile["h_index"] == 12
    assert profile["i10_index"] == 15
    assert profile["since_year"] == 2021


def test_fetch_paper_citations(fake_scholar):
    paper = scholar.fetch_paper_citations("U", "U:abc")
    assert paper.pub_year == 2018
    assert paper.total_citations == 30
    assert paper.citations_by_year == {"2019": 10, "2021": 18}


def test_merge_keeps_counts_and_adds_new_papers(tmp_path):
    path = str(tmp_path / "citations.json")
    data = {
        "user_id": "U",
        "scraped_at": "2026-01-01T00:00:00+00:00",
        "papers": [
            {"title": "Old title", "citation_id": "U:abc", "total_citations": 5,
             "citations_by_year": {"2020": 5}},
            {"title": "Removed", "citation_id": "U:zzz", "total_citations": 1,
             "citations_by_year": {"2020": 1}},
        ],
    }
    paper_list = [
        {"title": "Paper A", "citation_id": "U:abc", "pub_year": 2018},
        {"title": "Paper B", "citation_id": "U:def", "pub_year": None},
    ]
    merged = merge_paper_list(data, paper_list, {"h_index": 12}, "U", path)

    assert [p["citation_id"] for p in merged["papers"]] == ["U:abc", "U:def"]
    a, b = merged["papers"]
    assert a["title"] == "Paper A"
    assert a["pub_year"] == 2018
    assert a["citations_by_year"] == {"2020": 5}
    assert a["scraped_at"] == "2026-01-01T00:00:00+00:00"
    assert b["citations_by_year"] is None
    assert merged["profile"]["h_index"] == 12
    assert json.load(open(path)) == merged

    paper = Paper(title="Paper B", citation_id="U:def", total_citations=3,
                  citations_by_year={"2025": 3}, pub_year=2024)
    update_paper_progress(merged, 1, paper, path)
    assert merged["papers"][1]["pub_year"] == 2024
    assert merged["papers"][1]["scraped_at"] == merged["scraped_at"]

    reset_citations(merged)
    assert all(p["citations_by_year"] is None for p in merged["papers"])
