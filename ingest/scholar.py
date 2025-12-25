"""Google Scholar scraping logic."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

try:
    import browser_cookie3
    HAS_BROWSER_COOKIES = True
except ImportError:
    HAS_BROWSER_COOKIES = False

BASE_URL = "https://scholar.google.com"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# Create a session to maintain cookies
session = requests.Session()
session.headers.update(HEADERS)


def load_browser_cookies() -> bool:
    """Load cookies from browser for google.com domain."""
    if not HAS_BROWSER_COOKIES:
        print("browser_cookie3 not installed, skipping browser cookies")
        return False

    # Try different browsers in order of preference
    browsers = [
        ("Chrome", browser_cookie3.chrome),
        ("Firefox", browser_cookie3.firefox),
        ("Safari", browser_cookie3.safari),
    ]

    for name, browser_fn in browsers:
        try:
            cookies = browser_fn(domain_name=".google.com")
            session.cookies.update(cookies)
            print(f"Loaded cookies from {name}")
            return True
        except Exception:
            continue

    print("Could not load cookies from any browser")
    return False


class RateLimitError(Exception):
    """Raised when Google Scholar rate limits requests."""
    pass


def fetch_with_retry(url: str, max_retries: int = 5, base_delay: float = 10, verbose: bool = True) -> requests.Response:
    """Fetch URL with exponential backoff on 429 errors."""
    if verbose:
        print(f"  Fetching: {url}")

    for attempt in range(max_retries):
        response = session.get(url)

        if verbose:
            print(f"  Response: status={response.status_code}, url={response.url[:80]}...")

        # Check for rate limiting (429 or redirect to /sorry CAPTCHA page)
        if response.status_code == 429 or "/sorry/" in response.url:
            if attempt < max_retries - 1:
                wait_time = base_delay * (2 ** attempt)
                print(f"  Rate limited, waiting {wait_time}s before retry ({attempt + 1}/{max_retries})...")
                time.sleep(wait_time)
                continue
            else:
                raise RateLimitError(
                    "Google Scholar is rate limiting requests. "
                    "Try again in a few hours, or visit scholar.google.com in a browser "
                    "to solve the CAPTCHA, then retry."
                )

        response.raise_for_status()
        return response

    raise RateLimitError("Failed after max retries due to rate limiting")


@dataclass
class Paper:
    """Represents a paper with citation data."""

    title: str
    citation_id: str
    total_citations: int
    citations_by_year: dict[str, int]


def fetch_paper_list(user_id: str, delay: float = 5) -> list[dict]:
    """Fetch list of all papers for a Google Scholar user.

    Args:
        user_id: Google Scholar user ID.
        delay: Seconds to wait between paginated requests.

    Returns:
        List of dicts with 'title' and 'citation_id' for each paper.
    """
    papers = []
    start = 0
    page_size = 20  # Use smaller page size to reduce rate limiting

    while True:
        url = f"{BASE_URL}/citations?user={user_id}&hl=en&cstart={start}&pagesize={page_size}"
        response = fetch_with_retry(url)

        soup = BeautifulSoup(response.text, "html.parser")

        # Find paper entries in the table
        rows = soup.select("tr.gsc_a_tr")
        if not rows:
            break

        for row in rows:
            title_link = row.select_one("a.gsc_a_at")
            if title_link:
                title = title_link.get_text(strip=True)
                href = title_link.get("href", "")
                # Extract citation_for_view ID from href
                match = re.search(r"citation_for_view=([^&]+)", href)
                if match:
                    citation_id = match.group(1)
                    papers.append({"title": title, "citation_id": citation_id})

        # Check if there are more pages
        if len(rows) < page_size:
            break

        start += page_size
        time.sleep(delay)

    return papers


def fetch_paper_citations(user_id: str, citation_id: str) -> Paper:
    """Fetch citation details for a specific paper.

    Args:
        user_id: Google Scholar user ID.
        citation_id: The citation_for_view ID for the paper.

    Returns:
        Paper object with title, total citations, and yearly breakdown.
    """
    url = f"{BASE_URL}/citations?view_op=view_citation&hl=en&user={user_id}&citation_for_view={citation_id}"
    response = fetch_with_retry(url)

    soup = BeautifulSoup(response.text, "html.parser")

    # Get paper title
    title_elem = soup.select_one("#gsc_oci_title")
    title = title_elem.get_text(strip=True) if title_elem else "Unknown"

    # Get total citations
    total_citations = 0
    cited_by = soup.select_one("a:-soup-contains('Cited by')")
    if cited_by:
        match = re.search(r"Cited by (\d+)", cited_by.get_text())
        if match:
            total_citations = int(match.group(1))

    # Get citations by year from the histogram
    citations_by_year = {}
    graph_bars = soup.select("#gsc_oci_graph_bars a")
    for bar in graph_bars:
        href = bar.get("href", "")
        year_match = re.search(r"as_ylo=(\d{4})&as_yhi=(\d{4})", href)
        if year_match and year_match.group(1) == year_match.group(2):
            year = year_match.group(1)
            # Get citation count from the span
            count_span = bar.select_one("span.gsc_oci_g_al")
            if count_span:
                try:
                    count = int(count_span.get_text(strip=True))
                    citations_by_year[year] = count
                except ValueError:
                    pass

    return Paper(
        title=title,
        citation_id=citation_id,
        total_citations=total_citations,
        citations_by_year=citations_by_year,
    )


def scrape_user_citations(user_id: str, delay: float = 5) -> list[Paper]:
    """Scrape all citation data for a Google Scholar user.

    Args:
        user_id: Google Scholar user ID.
        delay: Seconds to wait between requests.

    Returns:
        List of Paper objects with citation data.
    """
    # Try to load browser cookies for authentication
    load_browser_cookies()

    print(f"Fetching paper list for user {user_id}...")
    paper_list = fetch_paper_list(user_id, delay)
    print(f"Found {len(paper_list)} papers")

    papers = []
    for i, paper_info in enumerate(paper_list, 1):
        print(f"Fetching citations for paper {i}/{len(paper_list)}: {paper_info['title'][:50]}...")
        paper = fetch_paper_citations(user_id, paper_info["citation_id"])
        papers.append(paper)
        if i < len(paper_list):
            time.sleep(delay)

    return papers
