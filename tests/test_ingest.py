import json
import sys

import pytest

import ingest.cli as cli
import ingest.scholar as scholar
from ingest.output import (
    ListCheckError,
    mark_all_stale,
    merge_paper_list,
    papers_to_fetch,
    update_paper_progress,
)
from ingest.scholar import Paper, parse_year


class FakeScholar:
    """Serves profile list and paper pages from a dict of papers, counting requests."""

    def __init__(self, papers):
        # citation_id -> {"title", "year", "by_year": {year: count}}
        self.papers = papers
        self.requests = []

    def count(self, cid):
        return sum(self.papers[cid]["by_year"].values())

    def list_page(self, start):
        if start > 0:
            return ""
        total = sum(self.count(cid) for cid in self.papers)
        rows = "".join(
            f'<tr class="gsc_a_tr">'
            f'<td class="gsc_a_t"><a class="gsc_a_at" href="/citations?citation_for_view={cid}">{p["title"]}</a></td>'
            f'<td class="gsc_a_c"><a class="gsc_a_ac">{self.count(cid) or ""}</a>'
            f'<span class="gsc_a_m">*</span></td>'
            f'<td class="gsc_a_y"><span class="gsc_a_h">{p.get("year") or ""}</span></td></tr>'
            for cid, p in self.papers.items()
        )
        return f"""
            <table id="gsc_rsb_st">
              <tr><th></th><th>All</th><th>Since 2021</th></tr>
              <tr><td>Citations</td><td class="gsc_rsb_std">{total}</td><td class="gsc_rsb_std">{total}</td></tr>
              <tr><td>h-index</td><td class="gsc_rsb_std">2</td><td class="gsc_rsb_std">2</td></tr>
              <tr><td>i10-index</td><td class="gsc_rsb_std">1</td><td class="gsc_rsb_std">1</td></tr>
            </table>
            <table>{rows}</table>
        """

    def paper_page(self, cid):
        p = self.papers[cid]
        bars = "".join(
            f'<a href="/scholar?as_ylo={y}&amp;as_yhi={y}"><span class="gsc_oci_g_al">{c}</span></a>'
            for y, c in p["by_year"].items() if c
        )
        return f"""
            <div id="gsc_oci_title">{p["title"]}</div>
            <div id="gsc_oci_table">
              <div class="gs_scl"><div class="gsc_oci_field">Publication date</div>
                <div class="gsc_oci_value">{p.get("detail_year", p.get("year"))}/6/1</div></div>
              <div class="gs_scl"><div class="gsc_oci_field">Total citations</div>
                <div class="gsc_oci_value"><a>Cited by {self.count(cid)}</a></div></div>
            </div>
            <div id="gsc_oci_graph_bars">{bars}</div>
        """

    def fetch(self, url, **kwargs):
        self.requests.append(url)
        if "view_citation" in url:
            cid = url.split("citation_for_view=")[1]
            return FakeResponse(self.paper_page(cid))
        start = int(url.split("cstart=")[1].split("&")[0])
        return FakeResponse(self.list_page(start))

    def detail_requests(self):
        return [u for u in self.requests if "view_citation" in u]


class FakeResponse:
    def __init__(self, text):
        self.text = text


def make_scholar():
    return FakeScholar({
        "U:a": {"title": "Paper A", "year": 2018, "by_year": {"2019": 10, "2021": 18}},
        "U:b": {"title": "Paper B", "year": None, "detail_year": 2020, "by_year": {"2021": 3}},
        "U:c": {"title": "Paper C", "year": 2024, "by_year": {}},
    })


@pytest.fixture
def fake(monkeypatch):
    fake = make_scholar()
    monkeypatch.setattr(scholar, "fetch_with_retry", fake.fetch)
    monkeypatch.setattr(scholar.time, "sleep", lambda s: None)
    monkeypatch.setattr(cli, "load_browser_cookies", lambda: None)
    return fake


def run_cli(monkeypatch, path, *flags):
    monkeypatch.setattr(sys, "argv", ["ingest", "--user", "U", "--config", "none.yaml",
                                      "--output", str(path), *flags])
    cli.main()
    return json.load(open(path))


def test_parse_year():
    assert parse_year("2018/12/1") == 2018
    assert parse_year("2020") == 2020
    assert parse_year("") is None


def test_fetch_paper_list(fake):
    papers, profile = scholar.fetch_paper_list("U", 0)
    assert papers == [
        {"title": "Paper A", "citation_id": "U:a", "pub_year": 2018, "citations": 28},
        {"title": "Paper B", "citation_id": "U:b", "pub_year": None, "citations": 3},
        {"title": "Paper C", "citation_id": "U:c", "pub_year": 2024, "citations": 0},
    ]
    assert profile["citations"] == 31
    assert profile["since_year"] == 2021


def test_missing_count_cell_is_unknown():
    from bs4 import BeautifulSoup
    row = BeautifulSoup('<tr class="gsc_a_tr"><td class="gsc_a_c"></td></tr>', "html.parser")
    assert scholar.parse_list_citations(row) is None


def test_fetch_paper_citations(fake):
    paper = scholar.fetch_paper_citations("U", "U:a")
    assert paper.pub_year == 2018
    assert paper.total_citations == 28
    assert paper.citations_by_year == {"2019": 10, "2021": 18}


def test_first_run_fetches_cited_papers(fake, monkeypatch, tmp_path):
    data = run_cli(monkeypatch, tmp_path / "c.json")
    assert len(fake.detail_requests()) == 2  # Paper C is uncited
    a, b, c = data["papers"]
    assert a["citations_by_year"] == {"2019": 10, "2021": 18}
    assert a["listed_citations"] == 28
    assert b["pub_year"] == 2020  # from the detail page
    assert c["citations_by_year"] == {}
    assert not any(p.get("stale") for p in data["papers"])


def test_second_run_only_fetches_changed_papers(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    first = run_cli(monkeypatch, path)

    fake.requests.clear()
    second = run_cli(monkeypatch, path)
    assert fake.detail_requests() == []
    # Unchanged histograms are current through the new list fetch
    assert second["papers"][0]["scraped_at"] > first["papers"][0]["scraped_at"]
    assert second["papers"][0]["fetched_at"] == first["papers"][0]["fetched_at"]

    fake.papers["U:b"]["by_year"]["2026"] = 2
    fake.requests.clear()
    third = run_cli(monkeypatch, path)
    assert fake.detail_requests() == [u for u in fake.requests if "U:b" in u]
    assert len(fake.detail_requests()) == 1
    assert third["papers"][1]["citations_by_year"] == {"2021": 3, "2026": 2}
    assert third["papers"][1]["listed_citations"] == 5


def test_refresh_is_resumable_and_keeps_data(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    run_cli(monkeypatch, path)

    # Rate limited after the first detail page of a refresh
    calls = {"n": 0}
    fetch = fake.fetch

    def limited(url, **kwargs):
        if "view_citation" in url:
            calls["n"] += 1
            if calls["n"] > 1:
                raise scholar.RateLimitError("limited")
        return fetch(url, **kwargs)

    monkeypatch.setattr(scholar, "fetch_with_retry", limited)
    with pytest.raises(SystemExit):
        run_cli(monkeypatch, path, "--refresh")
    data = json.load(open(path))
    assert all(p["citations_by_year"] is not None for p in data["papers"])
    assert sum(bool(p.get("stale")) for p in data["papers"]) == 1

    # A plain run finishes the refresh
    monkeypatch.setattr(scholar, "fetch_with_retry", fake.fetch)
    fake.requests.clear()
    data = run_cli(monkeypatch, path)
    assert len(fake.detail_requests()) == 1
    assert not any(p.get("stale") for p in data["papers"])


def _stored(**overrides):
    paper = {
        "title": "Paper A", "citation_id": "U:a", "total_citations": 28,
        "citations_by_year": {"2019": 10, "2021": 18},
        "scraped_at": "2026-01-01T00:00:00+00:00",
    }
    paper.update(overrides)
    return {"user_id": "U", "scraped_at": "2026-01-01T00:00:00+00:00", "papers": [paper]}


def _listed(citations, cid="U:a"):
    return [{"title": "Paper A", "citation_id": cid, "pub_year": 2018, "citations": citations}]


def test_merge_falls_back_to_total_citations(tmp_path):
    path = str(tmp_path / "c.json")
    unchanged = merge_paper_list(_stored(), _listed(28), None, "U", path)["papers"][0]
    assert "stale" not in unchanged
    assert unchanged["fetched_at"] == "2026-01-01T00:00:00+00:00"
    assert unchanged["scraped_at"] > "2026-01-01T00:00:00+00:00"

    changed = merge_paper_list(_stored(), _listed(30), None, "U", path)["papers"][0]
    assert changed["stale"]
    assert changed["citations_by_year"] == {"2019": 10, "2021": 18}
    assert changed["scraped_at"] == "2026-01-01T00:00:00+00:00"

    unknown = merge_paper_list(_stored(), _listed(None), None, "U", path)["papers"][0]
    assert unknown["stale"]


def test_merge_compares_against_listed_count(tmp_path):
    # Detail total and list count disagree; compare list to list
    data = _stored(listed_citations=27)
    merged = merge_paper_list(data, _listed(27), None, "U", str(tmp_path / "c.json"))
    assert "stale" not in merged["papers"][0]


def test_stale_persists_until_fetched(tmp_path):
    path = str(tmp_path / "c.json")
    data = _stored()
    mark_all_stale(data)
    merged = merge_paper_list(data, _listed(28), None, "U", path)
    assert merged["papers"][0]["stale"]
    assert merged["papers"][0]["scraped_at"] == "2026-01-01T00:00:00+00:00"

    paper = Paper(title="Paper A", citation_id="U:a", total_citations=28,
                  citations_by_year={"2019": 10, "2021": 18})
    update_paper_progress(merged, 0, paper, path, 28)
    assert "stale" not in merged["papers"][0]
    assert merged["papers"][0]["fetched_at"] == merged["papers"][0]["scraped_at"]


def test_fetch_priority():
    data = {"papers": [
        {"citation_id": "refresh", "citations_by_year": {}, "total_citations": 50,
         "listed_citations": 50, "stale": True},
        {"citation_id": "small", "citations_by_year": {}, "listed_citations": 10, "stale": True},
        {"citation_id": "big", "citations_by_year": {}, "listed_citations": 10, "stale": True},
        {"citation_id": "new", "citations_by_year": None},
        {"citation_id": "same", "citations_by_year": {}, "listed_citations": 5},
    ]}
    counts = {"refresh": 50, "small": 11, "big": 30, "new": 4, "same": 5}
    order = [data["papers"][i]["citation_id"] for i in papers_to_fetch(data, counts)]
    assert order == ["new", "big", "small", "refresh"]


def test_rejects_truncated_list(tmp_path):
    data = _stored()
    data["papers"] *= 20
    with pytest.raises(ListCheckError):
        merge_paper_list(data, _listed(28), None, "U", str(tmp_path / "c.json"))
    assert not (tmp_path / "c.json").exists()


def test_rejects_unparsed_counts(tmp_path):
    with pytest.raises(ListCheckError):
        merge_paper_list(None, _listed(None), {"citations": 28}, "U", str(tmp_path / "c.json"))
