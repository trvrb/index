"""Command line interface for the ingest tool."""

import argparse
import sys
import time

from .config import load_config
from .output import load_progress, merge_paper_list, reset_citations, update_paper_progress
from .scholar import (
    RateLimitError,
    fetch_paper_citations,
    fetch_paper_list,
    load_browser_cookies,
)


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
        help="Re-scrape citations for all papers (default: only papers not yet scraped)",
    )

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Command line user ID overrides config
    user_id = args.user or config["user_id"]
    delay = config.get("request_delay", 2)

    # Try to load browser cookies for authentication
    load_browser_cookies()

    # Stage 1: Fetch the paper list and merge it with existing progress
    data = load_progress(args.output)
    if data is not None and data.get("user_id") not in (None, user_id):
        print(f"{args.output} holds data for user {data['user_id']}; starting fresh")
        data = None
    if data is not None and args.refresh:
        print("Marking all papers for re-scraping")
        reset_citations(data)

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
    data = merge_paper_list(data, paper_list, profile, user_id, args.output)

    # Stage 2: Fetch citations for each paper that hasn't been scraped yet
    total = len(data["papers"])
    completed = sum(1 for p in data["papers"] if p["citations_by_year"] is not None)
    print(f"Progress: {completed}/{total} papers already scraped")

    if completed == total:
        print("All papers already scraped. Use --refresh to re-scrape citation counts.")
        return

    for i, paper_entry in enumerate(data["papers"]):
        if paper_entry["citations_by_year"] is not None:
            continue

        print(f"Fetching citations for paper {i + 1}/{total}: {paper_entry['title'][:60]}...")
        try:
            paper = fetch_paper_citations(user_id, paper_entry["citation_id"])
        except RateLimitError as e:
            completed = sum(1 for p in data["papers"] if p["citations_by_year"] is not None)
            print(f"\nRate limited: {e}")
            print(f"Progress saved: {completed}/{total} papers scraped.")
            print("Re-run without --refresh to resume from where you left off.")
            sys.exit(1)

        update_paper_progress(data, i, paper, args.output)
        completed += 1
        print(f"  Saved ({completed}/{total})")

        if completed < total:
            time.sleep(delay)

    print(f"\nDone! All {total} papers scraped. Results saved to {args.output}")


if __name__ == "__main__":
    main()
