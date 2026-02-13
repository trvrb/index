"""JSON output handling."""

import json
from datetime import datetime, timezone
from pathlib import Path

from .scholar import Paper


def save_citations(papers: list[Paper], user_id: str, output_path: str = "results/citations.json") -> None:
    """Save citation data to JSON file.

    Args:
        papers: List of Paper objects with citation data.
        user_id: Google Scholar user ID.
        output_path: Path to output JSON file.
    """
    data = {
        "user_id": user_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "papers": [
            {
                "title": paper.title,
                "total_citations": paper.total_citations,
                "citations_by_year": paper.citations_by_year,
            }
            for paper in papers
        ],
    }

    # Ensure output directory exists
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved citation data to {output_path}")


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


def init_progress(papers_metadata: list[dict], user_id: str, path: str) -> dict:
    """Create initial progress file with all papers having null citation data.

    Args:
        papers_metadata: List of dicts with 'title' and 'citation_id'.
        user_id: Google Scholar user ID.
        path: Output file path.

    Returns:
        The progress dict that was written.
    """
    data = {
        "user_id": user_id,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "papers": [
            {
                "title": p["title"],
                "citation_id": p["citation_id"],
                "total_citations": None,
                "citations_by_year": None,
            }
            for p in papers_metadata
        ],
    }

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w") as f:
        json.dump(data, f, indent=2)

    return data


def update_paper_progress(data: dict, index: int, paper: Paper, path: str) -> None:
    """Update a single paper's citation data in the progress file.

    Args:
        data: The full progress dict (modified in place).
        index: Index of the paper in data["papers"].
        paper: Paper object with scraped citation data.
        path: Output file path to re-write.
    """
    data["papers"][index]["total_citations"] = paper.total_citations
    data["papers"][index]["citations_by_year"] = paper.citations_by_year
    data["scraped_at"] = datetime.now(timezone.utc).isoformat()

    with open(path, "w") as f:
        json.dump(data, f, indent=2)
