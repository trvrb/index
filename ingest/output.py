"""Progress file handling.

The progress file (data/citations.json) keeps every paper's latest
citation histogram. Each run re-fetches the profile's paper list, which shows
every paper's "Cited by" count, and only re-fetches detail pages for papers
whose count changed. Data is never cleared before it's replaced, so an
interrupted run leaves a complete, partly stale dataset.

Per-paper fields:
    listed_citations: count on the profile list when the detail page was
        last fetched, used for change detection
    fetched_at: when the detail page was last fetched
    scraped_at: time through which the histogram is known to be current
    stale: true when the list shows a change that hasn't been fetched yet
    first_seen: when a never-scraped paper first appeared on the profile
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from .scholar import Paper


class ListCheckError(Exception):
    """Raised when a fetched paper list looks truncated or unparsed."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_progress(data: dict, path: str) -> None:
    """Write the progress file."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(data, f, indent=2)


def load_progress(path: str) -> dict | None:
    """Load existing progress file.

    Returns:
        Parsed JSON dict, or None if file doesn't exist.
    """
    p = Path(path)
    if not p.exists():
        return None
    with open(p) as f:
        return json.load(f)


def last_listed(paper: dict) -> Optional[int]:
    """List count when the paper's detail page was last fetched."""
    listed = paper.get("listed_citations")
    return paper.get("total_citations") if listed is None else listed


def is_pending(paper: dict) -> bool:
    """Whether a paper's detail page needs fetching."""
    return paper.get("citations_by_year") is None or bool(paper.get("stale"))


def mark_all_stale(data: dict) -> None:
    """Mark every scraped paper for re-fetching, keeping its current data."""
    for paper in data.get("papers", []):
        if paper.get("citations_by_year") is not None:
            paper["stale"] = True


def check_paper_list(data: Optional[dict], paper_list: list[dict], profile: Optional[dict]) -> None:
    """Guard against merging a truncated or unparsed paper list.

    Raises:
        ListCheckError: if the list has far fewer papers than stored, or its
            citation counts don't add up to the profile's total.
    """
    stored = len((data or {}).get("papers", []))
    if stored and len(paper_list) < 0.9 * stored:
        raise ListCheckError(
            f"Fetched {len(paper_list)} papers but {stored} are stored; "
            "the paper list may be incomplete"
        )
    if profile and profile.get("citations"):
        listed = sum(entry.get("citations") or 0 for entry in paper_list)
        if listed < 0.9 * profile["citations"]:
            raise ListCheckError(
                f"Listed citation counts sum to {listed} but the profile reports "
                f"{profile['citations']}; the list page layout may have changed"
            )


def scholar_updated(data: Optional[dict], paper_list: list[dict], profile: Optional[dict]) -> bool:
    """Whether Scholar's data changed since the stored scrape.

    Scholar refreshes citation counts every few days, not continuously. If no
    paper was added or removed and no listed count or profile total changed,
    Scholar hasn't refreshed: its counts are still as of the last refresh.
    With several new citations a day across a profile, a refresh that
    changes nothing is very unlikely.
    """
    if not data or not data.get("papers"):
        return True
    existing = {p.get("citation_id"): p for p in data["papers"]}
    if set(existing) != {entry["citation_id"] for entry in paper_list}:
        return True
    stored_profile = data.get("profile") or {}
    if profile and profile.get("citations") != stored_profile.get("citations"):
        return True
    for entry in paper_list:
        paper = existing[entry["citation_id"]]
        if is_pending(paper):
            continue  # its change was seen in an earlier run
        listed = entry.get("citations")
        if listed is None or listed != last_listed(paper):
            return True
    return False


def merge_paper_list(
    data: Optional[dict],
    paper_list: list[dict],
    profile: Optional[dict],
    user_id: str,
    path: str,
    updated: Optional[bool] = None,
) -> dict:
    """Merge a freshly fetched paper list into the progress file.

    Papers are matched by citation_id, and papers no longer on the profile
    are dropped. A paper is pending (needs its detail page fetched) if it's
    new, never scraped, already stale, or its listed count differs from the
    count when it was last fetched. Pending papers keep their existing data.

    If Scholar has refreshed (see scholar_updated), unchanged papers have no
    new citations as of now, so their scraped_at moves to now. Otherwise
    Scholar's counts are still as of its last refresh, and timestamps stay.

    Args:
        data: Existing progress dict, or None to start fresh.
        paper_list: Dicts with 'title', 'citation_id', 'pub_year' and
            'citations' from fetch_paper_list.
        profile: Profile summary stats, if parsed.
        user_id: Google Scholar user ID.
        path: Output file path.
        updated: Whether Scholar has refreshed; computed if not given.

    Returns:
        The merged progress dict that was written.

    Raises:
        ListCheckError: if the paper list fails check_paper_list.
    """
    check_paper_list(data, paper_list, profile)
    if updated is None:
        updated = scholar_updated(data, paper_list, profile)

    now = _now()
    data = data or {}
    previous_scraped_at = data.get("scraped_at")
    # Without a refresh, Scholar's counts are still as of the stored scrape
    current_as_of = now if updated or not previous_scraped_at else previous_scraped_at
    existing = {p.get("citation_id"): p for p in data.get("papers", [])}

    papers = []
    for entry in paper_list:
        old = existing.get(entry["citation_id"], {})
        paper = {
            "title": entry["title"],
            "citation_id": entry["citation_id"],
            "pub_year": entry.get("pub_year") or old.get("pub_year"),
            "total_citations": old.get("total_citations"),
            "listed_citations": old.get("listed_citations"),
            "citations_by_year": old.get("citations_by_year"),
        }
        if paper["citations_by_year"] is not None:
            scraped_at = old.get("scraped_at") or previous_scraped_at
            if old.get("fetched_at"):
                paper["fetched_at"] = old["fetched_at"]
            elif old.get("listed_citations") is None:
                # Scraped before fetch times were recorded; its page was fetched then
                paper["fetched_at"] = scraped_at
            paper["scraped_at"] = scraped_at

            listed = entry.get("citations")
            changed = listed is None or listed != last_listed(old)
            if old.get("stale") or changed:
                paper["stale"] = True
            elif updated:
                paper["scraped_at"] = now
        else:
            # Lets the health check measure how long a new paper has waited
            paper["first_seen"] = old.get("first_seen") or now
        papers.append(paper)

    n_new = sum(1 for e in paper_list if e["citation_id"] not in existing)
    n_dropped = len(set(existing) - {e["citation_id"] for e in paper_list})
    if existing:
        print(f"  {n_new} new papers, {n_dropped} no longer listed")

    result = {
        "user_id": user_id,
        "scraped_at": current_as_of,
        "profile": (profile if updated else None) or data.get("profile"),
        "papers": papers,
    }
    if profile and updated:
        result["profile"]["scraped_at"] = now

    save_progress(result, path)
    return result


def papers_to_fetch(data: dict, list_counts: dict[str, Optional[int]]) -> list[int]:
    """Indices of pending papers, in the order to fetch them.

    Never-scraped papers come first, then papers with the largest change in
    listed citations, then papers marked by --refresh (most cited first), so
    an interrupted run gets the most important updates done.
    """
    def priority(i: int) -> tuple[int, int]:
        paper = data["papers"][i]
        listed = list_counts.get(paper["citation_id"])
        if paper.get("citations_by_year") is None:
            return (0, -(listed or 0))
        last = last_listed(paper)
        if listed is not None and last is not None and listed != last:
            return (1, -abs(listed - last))
        return (2, -(listed or paper.get("total_citations") or 0))

    pending = [i for i, paper in enumerate(data["papers"]) if is_pending(paper)]
    return sorted(pending, key=priority)


def papers_to_refresh(
    data: dict,
    list_counts: dict[str, Optional[int]],
    older_than_days: float,
    max_papers: int,
) -> list[int]:
    """Indices of up-to-date papers whose detail pages are due for a re-fetch.

    Scholar sometimes moves citations between years without changing a
    paper's total, which change detection can't see. Re-fetching a few of the
    oldest pages each run keeps every histogram fresh. Uncited papers are
    skipped, since they have no histogram to drift.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    due = []
    for i, paper in enumerate(data["papers"]):
        fetched_at = paper.get("fetched_at")
        if is_pending(paper) or not fetched_at or not list_counts.get(paper["citation_id"]):
            continue
        if datetime.fromisoformat(fetched_at) < cutoff:
            due.append(i)
    due.sort(key=lambda i: data["papers"][i]["fetched_at"])
    return due[:max_papers]


def oldest_pending_days(data: dict) -> float:
    """Days the longest-waiting pending paper has gone without an update.

    Stale papers are measured from when their counts were last current, and
    never-scraped papers from when they first appeared on the profile.
    """
    now = datetime.now(timezone.utc)
    ages = []
    for paper in data["papers"]:
        if not is_pending(paper):
            continue
        since = paper.get("scraped_at") if paper.get("citations_by_year") is not None else paper.get("first_seen")
        if since:
            ages.append((now - datetime.fromisoformat(since)).total_seconds() / 86400)
    return max(ages, default=0.0)


def record_uncited(data: dict, index: int, observed_at: Optional[str] = None) -> None:
    """Record a paper the list shows as uncited, without fetching its page.

    observed_at is when Scholar's counts were last refreshed, if not now.
    """
    paper = data["papers"][index]
    paper["total_citations"] = 0
    paper["listed_citations"] = 0
    paper["citations_by_year"] = {}
    paper["scraped_at"] = observed_at or _now()
    paper.pop("stale", None)
    paper.pop("first_seen", None)


def update_paper_progress(
    data: dict,
    index: int,
    paper: Paper,
    path: str,
    listed_citations: Optional[int] = None,
    observed_at: Optional[str] = None,
) -> None:
    """Update a single paper's citation data in the progress file.

    Args:
        data: The full progress dict (modified in place).
        index: Index of the paper in data["papers"].
        paper: Paper object with scraped citation data.
        path: Output file path to re-write.
        listed_citations: The paper's count on the profile list this run.
        observed_at: When Scholar's counts were last refreshed, if Scholar
            hasn't refreshed since; the histogram is current as of then.
    """
    now = _now()
    entry = data["papers"][index]
    entry["total_citations"] = paper.total_citations
    entry["listed_citations"] = (
        paper.total_citations if listed_citations is None else listed_citations
    )
    entry["citations_by_year"] = paper.citations_by_year
    entry["fetched_at"] = now
    entry["scraped_at"] = observed_at or now
    entry.pop("stale", None)
    entry.pop("first_seen", None)
    if entry.get("pub_year") is None and paper.pub_year is not None:
        entry["pub_year"] = paper.pub_year
    if observed_at is None:
        data["scraped_at"] = now

    save_progress(data, path)
