"""Command line interface for the ingest tool."""

import argparse
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from . import scholar
from .config import load_config
from .output import (
    ListCheckError,
    is_pending,
    load_progress,
    mark_all_stale,
    merge_paper_list,
    oldest_pending_days,
    papers_to_fetch,
    papers_to_refresh,
    record_uncited,
    save_progress,
    scholar_updated,
    update_paper_progress,
)
from .scholar import (
    BudgetExhausted,
    RateLimitError,
    UnexpectedPageError,
    fetch_paper_citations,
    fetch_paper_list,
    load_browser_cookies,
)

# Reasons to stop fetching and keep what's been saved
STOP_ERRORS = (RateLimitError, BudgetExhausted, UnexpectedPageError, requests.RequestException)

# Exit status when Scholar refused the paper list, so nothing was updated.
# Unattended runs treat this as a skipped run rather than a failure.
EXIT_SKIPPED = 75


def data_age_days(data: Optional[dict]) -> float:
    """Days since the stored data was last confirmed current by a paper-list fetch."""
    if not data or not data.get("scraped_at"):
        return float("inf")
    scraped_at = datetime.fromisoformat(data["scraped_at"])
    return (datetime.now(timezone.utc) - scraped_at).total_seconds() / 86400


def write_outputs(values: dict) -> None:
    """Write step outputs when running in GitHub Actions."""
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.writelines(f"{key}={value}\n" for key, value in values.items())


def report(data: dict, stats: dict, status: str) -> None:
    """Print a run summary, and write it for GitHub Actions when running there.

    status is "updated" when the data changed, or "unchanged" when Scholar
    hasn't refreshed and there was nothing to fetch.
    """
    pending = sum(1 for p in data["papers"] if is_pending(p))
    oldest = oldest_pending_days(data)
    used = scholar.settings.used
    budget = scholar.settings.max_requests

    rows = [
        ("Requests", f"{used}" + (f" of {budget}" if budget else "")),
        ("Fetched (new or changed)", stats["fetched"]),
        ("Refreshed (aged)", stats["refreshed"]),
        ("Unchanged", stats["unchanged"]),
        ("Uncited (no request)", stats["uncited"]),
        ("Skipped (inconsistent page)", stats["skipped"]),
        ("Still pending", pending),
        ("Oldest pending (days)", f"{oldest:.1f}"),
    ]
    print("\nSummary:")
    for name, value in rows:
        print(f"  {name}: {value}")
    if stats["stopped"]:
        print(f"  Stopped early: {stats['stopped']}")
    if pending:
        print(f"{pending} papers still need fetching; the next run continues with them.")

    if os.environ.get("GITHUB_ACTIONS") and pending:
        print(f"::warning::{pending} papers still pending (oldest {oldest:.0f} days)")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write("### Scholar scrape\n\n| | |\n|---|---|\n")
            f.writelines(f"| {name} | {value} |\n" for name, value in rows)
            if stats["stopped"]:
                f.write(f"\nStopped early: {stats['stopped']}\n")
    write_outputs({
        "status": status,
        "data_age_days": f"{data_age_days(data):.1f}",
        "fetched": stats["fetched"],
        "refreshed": stats["refreshed"],
        "pending": pending,
        "oldest_pending_days": f"{oldest:.1f}",
        "requests": used,
    })


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
        default="data/citations.json",
        help="Output JSON file path (default: data/citations.json)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-fetch every paper, not just those whose citation count changed",
    )
    parser.add_argument(
        "--max-requests",
        type=int,
        help="Most requests to make this run (overrides config max_requests)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        help="Attempts per page when rate limited (overrides config max_retries)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        help="Seconds between requests (overrides config request_delay)",
    )
    parser.add_argument(
        "--no-cookies",
        action="store_true",
        help="Don't load browser cookies (for unattended runs)",
    )

    args = parser.parse_args()

    # Load configuration; command line options override it
    config = load_config(args.config)
    user_id = args.user or config["user_id"]
    delay = args.delay if args.delay is not None else config["request_delay"]
    scholar.settings.max_requests = (
        args.max_requests if args.max_requests is not None else config["max_requests"]
    )
    scholar.settings.max_retries = (
        args.max_retries if args.max_retries is not None else config["max_retries"]
    )

    if not args.no_cookies:
        load_browser_cookies()

    data = load_progress(args.output)
    if data is not None and data.get("user_id") not in (None, user_id):
        print(f"{args.output} holds data for user {data['user_id']}; starting fresh")
        data = None

    # Stage 1: Fetch the paper list and find papers whose counts changed
    print(f"Fetching paper list for user {user_id}...")
    try:
        paper_list, profile = fetch_paper_list(user_id, delay)
    except STOP_ERRORS as e:
        age = data_age_days(data)
        print(f"\nCould not fetch the paper list: {e}")
        print(f"Nothing updated; stored data is {age:.1f} days old.")
        if os.environ.get("GITHUB_ACTIONS"):
            print(f"::warning::Skipped: Scholar refused the paper list ({e})")
        write_outputs({
            "status": "skipped",
            "data_age_days": f"{min(age, 9999):.1f}",
            "oldest_pending_days": f"{oldest_pending_days(data) if data else 0:.1f}",
        })
        sys.exit(EXIT_SKIPPED)
    print(f"Found {len(paper_list)} papers")
    if profile:
        print(f"Profile: {profile['citations']} citations, h-index {profile['h_index']}, "
              f"i10-index {profile['i10_index']}")

    if data is not None and args.refresh:
        print("Marking all papers for re-fetching")
        mark_all_stale(data)
    updated = scholar_updated(data, paper_list, profile)
    try:
        data = merge_paper_list(data, paper_list, profile, user_id, args.output, updated)
    except ListCheckError as e:
        print(f"\nNot updating {args.output}: {e}")
        sys.exit(1)

    # Without a Scholar refresh, counts are as of the last refresh, not now
    observed_at = None if updated else data["scraped_at"]
    if not updated:
        print(f"No counts changed on Scholar since the last update "
              f"({data['scraped_at'][:16].replace('T', ' ')} UTC)")

    list_counts = {entry["citation_id"]: entry.get("citations") for entry in paper_list}
    queue = papers_to_fetch(data, list_counts)

    # Papers the list shows as uncited don't need their detail page
    uncited = {i for i in queue if list_counts.get(data["papers"][i]["citation_id"]) == 0}
    for i in uncited:
        record_uncited(data, i, observed_at)
    if uncited:
        save_progress(data, args.output)
    queue = [i for i in queue if i not in uncited]

    # Refresh old pages only when Scholar has refreshed, so quiet days cost nothing
    refresh = papers_to_refresh(
        data, list_counts, config["refresh_after_days"], config["refresh_per_run"]
    ) if updated else []
    total = len(data["papers"])
    stats = {
        "fetched": 0,
        "refreshed": 0,
        "unchanged": total - len(queue) - len(uncited),
        "uncited": len(uncited),
        "skipped": 0,
        "stopped": None,
    }
    print(f"{len(queue)} of {total} papers need fetching "
          f"({stats['unchanged']} unchanged, {len(uncited)} uncited); "
          f"{len(refresh)} due for refresh")

    # Stage 2: Fetch changed papers, then refresh the oldest detail pages
    work = [(i, False) for i in queue] + [(i, True) for i in refresh]
    for n, (i, is_refresh) in enumerate(work, 1):
        paper_entry = data["papers"][i]
        time.sleep(delay)
        print(f"Fetching citations for paper {n}/{len(work)}"
              f"{' (refresh)' if is_refresh else ''}: {paper_entry['title'][:60]}...")
        try:
            paper = fetch_paper_citations(user_id, paper_entry["citation_id"])
        except STOP_ERRORS as e:
            stats["stopped"] = f"{type(e).__name__}: {e}"
            print(f"\nStopping: {stats['stopped']}")
            break

        listed = list_counts.get(paper_entry["citation_id"])
        if listed and not paper.total_citations:
            # Don't overwrite a cited paper with an empty page; retry next run
            print(f"  Skipped: list shows {listed} citations but the page shows none")
            stats["skipped"] += 1
            continue

        update_paper_progress(data, i, paper, args.output, listed, observed_at)
        stats["refreshed" if is_refresh else "fetched"] += 1
        print("  Saved")

    changed = updated or stats["fetched"] or stats["refreshed"] or stats["uncited"]
    if not changed:
        print("Nothing to update.")
    report(data, stats, "updated" if changed else "unchanged")


if __name__ == "__main__":
    main()
