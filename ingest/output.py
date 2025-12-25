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
