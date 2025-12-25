"""Command line interface for the ingest tool."""

import argparse

from .config import load_config
from .output import save_citations
from .scholar import scrape_user_citations


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

    args = parser.parse_args()

    # Load configuration
    config = load_config(args.config)

    # Command line user ID overrides config
    user_id = args.user or config["user_id"]
    delay = config.get("request_delay", 2)

    # Scrape citations
    papers = scrape_user_citations(user_id, delay)

    # Save output
    save_citations(papers, user_id, args.output)


if __name__ == "__main__":
    main()
