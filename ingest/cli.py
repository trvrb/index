"""Command line interface for the ingest tool."""

import argparse
import sys
import time
from datetime import datetime, timedelta, timezone

from .config import load_config
from .output import (
    ListCheckError,
    load_progress,
    mark_all_stale,
    merge_paper_list,
    papers_to_fetch,
    record_uncited,
    save_progress,
    update_paper_progress,
)
from .scholar import (
    RateLimitError,
    fetch_paper_citations,
    fetch_paper_list,
    load_browser_cookies,
)

# Suggest a full refresh when a detail page hasn't been fetched for this long
REFRESH_AFTER_DAYS = 180


def print_refresh_nudge(data: dict) -> None:
    """Suggest --refresh if some detail pages are old.

    Scholar sometimes moves citations between years without changing a
    paper's total, which change detection can't see.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=REFRESH_AFTER_DAYS)
    fetched = [
        datetime.fromisoformat(p["fetched_at"])
        for p in data["papers"]
        if p.get("fetched_at")
    ]
    old = [t for t in fetched if t < cutoff]
    if old:
        print(f"{len(old)} papers were last fetched more than {REFRESH_AFTER_DAYS} days ago "
              f"(oldest {min(old).date()}); consider running with --refresh")


def main() -> None:
    """Run the Google Scholar citation scraper."""
    parser = argparse.ArgumentParser(
        description="Scrape Google Scholar citation data for a user"
    )
    parser.add_argument(
        "--config",
        "-c",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--user",
        "-u",
        help="Google Scholar user ID (overrides config)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="results/citations.json",
        help="Output JSON file path (default: results/citations.json)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch every paper, not just those whose citation count changed",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Command line user ID overrides config
    user_id = args.user or config["user_id"]
    delay = config.get("request_delay", 2)

    # Try to load browser cookies for authentication
    load_browser_cookies()

    data = load_progress(args.output)
    if data is not None and data.get("user_id") not in (None, user_id):
        print(f"{args.output} holds data for user {data['user_id']}; starting fresh")
        data = None

    # Stage 1: Fetch the paper list and find papers whose counts changed
    print(f"Fetching paper list for user {user_id}...")
    try:
        paper_list, profile = fetch_paper_list(user_id, delay)
    except RateLimitError as e:
        print(f"\nRate limited: {e}")
        sys.exit(1)
    print(f"Found {len(paper_list)} papers")
    if profile:
        print(f"Profile: {profile['citations']} citations, h-index {profile['h_index']}, "
              f"i10-index {profile['i10_index']}")

    if data is not None and args.refresh:
        print("Marking all papers for re-fetching")
        mark_all_stale(data)
    try:
        data = merge_paper_list(data, paper_list, profile, user_id, args.output)
    except ListCheckError as e:
        print(f"\nNot updating {args.output}: {e}")
        sys.exit(1)

    list_counts = {entry["citation_id"]: entry.get("citations") for entry in paper_list}
    queue = papers_to_fetch(data, list_counts)

    # Papers the list shows as uncited don't need their detail page
    uncited = {i for i in queue if list_counts.get(data["papers"][i]["citation_id"]) == 0}
    for i in uncited:
        record_uncited(data, i)
    if uncited:
        save_progress(data, args.output)
    queue = [i for i in queue if i not in uncited]

    total = len(data["papers"])
    print(f"{len(queue)} of {total} papers need fetching "
          f"({total - len(queue) - len(uncited)} unchanged, {len(uncited)} uncited)")

    # Stage 2: Fetch citations for changed papers
    for n, i in enumerate(queue, 1):
        paper_entry = data["papers"][i]
        print(f"Fetching citations for paper {n}/{len(queue)}: {paper_entry['title'][:60]}...")
        try:
            paper = fetch_paper_citations(user_id, paper_entry["citation_id"])
        except RateLimitError as e:
            print(f"\nRate limited: {e}")
            print(f"Progress saved: {n - 1}/{len(queue)} papers fetched. "
                  f"Re-run `python -m ingest` to fetch the remaining {len(queue) - n + 1}.")
            sys.exit(1)

        update_paper_progress(
            data, i, paper, args.output, list_counts.get(paper_entry["citation_id"])
        )
        print("  Saved")

        if n < len(queue):
            time.sleep(delay)

    print(f"\nDone! All {total} papers up to date. Results saved to {args.output}")
    print_refresh_nudge(data)


if __name__ == "__main__":
    main()
