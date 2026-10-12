import json
import sys
from datetime import datetime, timedelta, timezone

import pytest
import requests

import ingest.cli as cli
import ingest.scholar as scholar
from ingest.output import (
    ListCheckError,
    mark_all_stale,
    merge_paper_list,
    oldest_pending_days,
    papers_to_fetch,
    papers_to_refresh,
    update_paper_progress,
)
from ingest.scholar import Paper, parse_year


class FakeResponse:
    def __init__(self, text, status_code=200, url="https://scholar.google.com/citations"):
        self.text = text
        self.status_code = status_code
        self.url = url

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"status {self.status_code}")


class FakeScholar:
    """Serves profile list and paper pages from a dict of papers, recording requests.

    Set `detail_response` to a function (citation_id -> FakeResponse or
    exception) to simulate blocks and broken pages.
    """

    def __init__(self, papers):
        # citation_id -> {"title", "year", "by_year": {year: count}}
        self.papers = papers
        self.requests = []
        self.detail_response = None

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

    def get(self, url, timeout=None):
        self.requests.append(url)
        if "view_citation" in url:
            cid = url.split("citation_for_view=")[1]
            if self.detail_response:
                result = self.detail_response(cid)
                if isinstance(result, Exception):
                    raise result
                return result
            return FakeResponse(self.paper_page(cid), url=url)
        start = int(url.split("cstart=")[1].split("&")[0])
        return FakeResponse(self.list_page(start), url=url)

    def detail_requests(self):
        return [u for u in self.requests if "view_citation" in u]


def make_scholar():
    return FakeScholar({
        "U:a": {"title": "Paper A", "year": 2018, "by_year": {"2019": 10, "2021": 18}},
        "U:b": {"title": "Paper B", "year": None, "detail_year": 2020, "by_year": {"2021": 3}},
        "U:c": {"title": "Paper C", "year": 2024, "by_year": {}},
    })


@pytest.fixture
def fake(monkeypatch):
    fake = make_scholar()
    monkeypatch.setattr(scholar.session, "get", fake.get)
    monkeypatch.setattr(scholar, "settings", scholar.RequestSettings())
    monkeypatch.setattr(scholar.time, "sleep", lambda s: None)
    monkeypatch.setattr(cli, "load_browser_cookies", lambda: None)
    for var in ("GITHUB_ACTIONS", "GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"):
        monkeypatch.delenv(var, raising=False)
    return fake


def run_cli(monkeypatch, path, *flags):
    monkeypatch.setattr(sys, "argv", ["ingest", "--user", "U", "--config", "none.yaml",
                                      "--output", str(path), *flags])
    monkeypatch.setattr(scholar, "settings", scholar.RequestSettings())
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
    assert "pagesize=100" in fake.requests[0]


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
    assert not any(p.get("stale") or p.get("first_seen") for p in data["papers"])


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
    assert len(fake.detail_requests()) == 1
    assert "U:b" in fake.detail_requests()[0]
    assert third["papers"][1]["citations_by_year"] == {"2021": 3, "2026": 2}
    assert third["papers"][1]["listed_citations"] == 5


def _first_run_then_change(fake, monkeypatch, path):
    run_cli(monkeypatch, path)
    fake.papers["U:a"]["by_year"]["2026"] = 4
    fake.papers["U:b"]["by_year"]["2026"] = 1
    fake.requests.clear()


def test_budget_stops_and_keeps_pending(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _first_run_then_change(fake, monkeypatch, path)
    outputs = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))

    data = run_cli(monkeypatch, path, "--max-requests", "2")  # list page + one paper
    assert len(fake.requests) == 2
    stale = [p["citation_id"] for p in data["papers"] if p.get("stale")]
    assert stale == ["U:b"]  # the larger change (U:a) was fetched first
    written = dict(line.split("=", 1) for line in outputs.read_text().splitlines())
    assert written["status"] == "updated" and written["pending"] == "1"

    fake.requests.clear()
    data = run_cli(monkeypatch, path)
    assert len(fake.detail_requests()) == 1
    assert not any(p.get("stale") for p in data["papers"])


def test_single_429_stops_without_retrying(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _first_run_then_change(fake, monkeypatch, path)
    before = json.load(open(path))
    fake.detail_response = lambda cid: FakeResponse("", status_code=429)

    data = run_cli(monkeypatch, path, "--max-retries", "1")
    assert len(fake.detail_requests()) == 1
    for old, new in zip(before["papers"], data["papers"]):
        assert new["citations_by_year"] == old["citations_by_year"]
    assert sum(bool(p.get("stale")) for p in data["papers"]) == 2


@pytest.mark.parametrize("page", [
    FakeResponse("<html>Our systems have detected unusual traffic</html>"),
    FakeResponse('<form id="gs_captcha_f"></form>'),
    FakeResponse("<html>no paper here</html>"),
])
def test_block_pages_leave_data_untouched(fake, monkeypatch, tmp_path, page):
    path = tmp_path / "c.json"
    _first_run_then_change(fake, monkeypatch, path)
    before = json.load(open(path))
    fake.detail_response = lambda cid: page

    data = run_cli(monkeypatch, path, "--max-retries", "1")
    assert len(fake.detail_requests()) == 1  # the run stops at the first bad page
    for old, new in zip(before["papers"], data["papers"]):
        assert new["citations_by_year"] == old["citations_by_year"]


def test_empty_page_for_cited_paper_is_skipped(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _first_run_then_change(fake, monkeypatch, path)
    page_a = '<div id="gsc_oci_title">Paper A</div>'  # title but no citations
    fake.detail_response = lambda cid: (
        FakeResponse(page_a) if cid == "U:a" else FakeResponse(fake.paper_page(cid))
    )

    data = run_cli(monkeypatch, path)
    assert len(fake.detail_requests()) == 2  # skips Paper A and carries on
    a, b, _ = data["papers"]
    assert a["citations_by_year"] == {"2019": 10, "2021": 18} and a["stale"]
    assert b["citations_by_year"] == {"2021": 3, "2026": 1}


def test_connection_error_keeps_progress(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    _first_run_then_change(fake, monkeypatch, path)
    fake.detail_response = lambda cid: requests.ConnectionError("reset")

    data = run_cli(monkeypatch, path)
    assert sum(bool(p.get("stale")) for p in data["papers"]) == 2
    assert data["papers"][2]["scraped_at"] > "2026"  # merge still recorded


@pytest.mark.parametrize("status", [403, 429])
def test_refused_list_skips_without_writing(fake, monkeypatch, tmp_path, status):
    path = tmp_path / "c.json"
    run_cli(monkeypatch, path)
    before = path.read_text()
    outputs = tmp_path / "github_output"
    monkeypatch.setenv("GITHUB_OUTPUT", str(outputs))
    monkeypatch.setattr(scholar.session, "get", lambda url, timeout=None: FakeResponse("", status))

    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, path, "--max-retries", "1")
    assert exit_info.value.code == cli.EXIT_SKIPPED
    assert path.read_text() == before
    written = dict(line.split("=", 1) for line in outputs.read_text().splitlines())
    assert written["status"] == "skipped"
    assert float(written["data_age_days"]) < 0.01


def test_truncated_list_fails(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    run_cli(monkeypatch, path)
    before = path.read_text()
    for cid in ["U:b", "U:c"]:
        del fake.papers[cid]  # list now shows 1 of 3 stored papers

    with pytest.raises(SystemExit) as exit_info:
        run_cli(monkeypatch, path)
    assert exit_info.value.code == 1
    assert path.read_text() == before


def test_refresh_is_resumable_and_keeps_data(fake, monkeypatch, tmp_path):
    path = tmp_path / "c.json"
    run_cli(monkeypatch, path)

    # Rate limited after the first detail page of a refresh
    calls = {"n": 0}

    def limited(cid):
        calls["n"] += 1
        if calls["n"] > 1:
            return FakeResponse("", status_code=429)
        return FakeResponse(fake.paper_page(cid))

    fake.detail_response = limited
    data = run_cli(monkeypatch, path, "--refresh", "--max-retries", "1")
    assert all(p["citations_by_year"] is not None for p in data["papers"])
    assert sum(bool(p.get("stale")) for p in data["papers"]) == 1

    # A plain run finishes the refresh
    fake.detail_response = None
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


def test_new_papers_get_first_seen(tmp_path):
    path = str(tmp_path / "c.json")
    merged = merge_paper_list(_stored(), _listed(28) + _listed(5, cid="U:new"), None, "U", path)
    new = merged["papers"][1]
    assert new["citations_by_year"] is None and new["first_seen"]
    assert 0 <= oldest_pending_days(merged) < 0.01

    # first_seen survives later merges until the paper is fetched
    new["first_seen"] = "2026-01-01T00:00:00+00:00"
    again = merge_paper_list(merged, _listed(28) + _listed(5, cid="U:new"), None, "U", path)
    assert again["papers"][1]["first_seen"] == "2026-01-01T00:00:00+00:00"
    assert oldest_pending_days(again) > 30

    paper = Paper(title="New", citation_id="U:new", total_citations=5, citations_by_year={"2026": 5})
    update_paper_progress(again, 1, paper, path, 5)
    assert "first_seen" not in again["papers"][1]


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


def test_rolling_refresh_selection():
    now = datetime.now(timezone.utc)
    ago = lambda days: (now - timedelta(days=days)).isoformat()
    data = {"papers": [
        {"citation_id": "old", "citations_by_year": {}, "fetched_at": ago(200)},
        {"citation_id": "older", "citations_by_year": {}, "fetched_at": ago(300)},
        {"citation_id": "recent", "citations_by_year": {}, "fetched_at": ago(10)},
        {"citation_id": "uncited", "citations_by_year": {}, "fetched_at": ago(400)},
        {"citation_id": "pending", "citations_by_year": {}, "fetched_at": ago(500), "stale": True},
        {"citation_id": "aged", "citations_by_year": {}, "fetched_at": ago(100)},
    ]}
    counts = {"old": 5, "older": 5, "recent": 5, "uncited": 0, "pending": 9, "aged": 5}
    order = [data["papers"][i]["citation_id"] for i in papers_to_refresh(data, counts, 90, 2)]
    assert order == ["older", "old"]


def test_rejects_truncated_list(tmp_path):
    data = _stored()
    data["papers"] *= 20
    with pytest.raises(ListCheckError):
        merge_paper_list(data, _listed(28), None, "U", str(tmp_path / "c.json"))
    assert not (tmp_path / "c.json").exists()


def test_rejects_unparsed_counts(tmp_path):
    with pytest.raises(ListCheckError):
        merge_paper_list(None, _listed(None), {"citations": 28}, "U", str(tmp_path / "c.json"))
