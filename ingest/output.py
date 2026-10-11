"""JSON output handling."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .scholar import Paper


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(data: dict, path: str) -> None:
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


def reset_citations(data: dict) -> None:
    """Mark every paper as unscraped so its citations are fetched again."""
    for paper in data.get("papers", []):
        paper["total_citations"] = None
        paper["citations_by_year"] = None
        paper.pop("scraped_at", None)


def merge_paper_list(
    data: Optional[dict],
    paper_list: list[dict],
    profile: Optional[dict],
    user_id: str,
    path: str,
) -> dict:
    """Merge a freshly fetched paper list into the progress file.

    Papers are matched by citation_id. Existing citation data is kept, new
    papers are added unscraped, and papers no longer on the profile are
    dropped. Titles and publication years come from the fresh list.

    Args:
        data: Existing progress dict, or None to start fresh.
        paper_list: Dicts with 'title', 'citation_id' and 'pub_year'.
        profile: Profile summary stats, if parsed.
        user_id: Google Scholar user ID.
        path: Output file path.

    Returns:
        The merged progress dict that was written.
    """
    data = data or {}
    previous_scraped_at = data.get("scraped_at")
    existing = {p.get("citation_id"): p for p in data.get("papers", [])}

    papers = []
    for entry in paper_list:
        paper = existing.get(entry["citation_id"], {})
        merged = {
            "title": entry["title"],
            "citation_id": entry["citation_id"],
            "pub_year": entry.get("pub_year") or paper.get("pub_year"),
            "total_citations": paper.get("total_citations"),
            "citations_by_year": paper.get("citations_by_year"),
        }
        # Kept counts were observed at the previous scrape time
        if merged["citations_by_year"] is not None:
            merged["scraped_at"] = paper.get("scraped_at") or previous_scraped_at
        papers.append(merged)

    n_new = sum(1 for e in paper_list if e["citation_id"] not in existing)
    n_dropped = len(set(existing) - {e["citation_id"] for e in paper_list})
    if existing:
        print(f"  {n_new} new papers, {n_dropped} no longer listed")

    result = {
        "user_id": user_id,
        "scraped_at": previous_scraped_at or _now(),
        "profile": profile or data.get("profile"),
        "papers": papers,
    }
    if profile:
        result["profile"]["scraped_at"] = _now()

    _write(result, path)
    return result


def update_paper_progress(data: dict, index: int, paper: Paper, path: str) -> None:
    """Update a single paper's citation data in the progress file.

    Args:
        data: The full progress dict (modified in place).
        index: Index of the paper in data["papers"].
        paper: Paper object with scraped citation data.
        path: Output file path to re-write.
    """
    now = _now()
    entry = data["papers"][index]
    entry["total_citations"] = paper.total_citations
    entry["citations_by_year"] = paper.citations_by_year
    entry["scraped_at"] = now
    if entry.get("pub_year") is None and paper.pub_year is not None:
        entry["pub_year"] = paper.pub_year
    data["scraped_at"] = now

    _write(data, path)
