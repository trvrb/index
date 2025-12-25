# index

A tool for tracking and visualizing Google Scholar citation data over time.

## Overview

This project has two components:

1. **Python scraper** - A command line tool that collects citation data from Google Scholar
2. **D3.js visualization** - A web-based chart for displaying citation trends, deployable via GitHub Pages

## Data Scraper

The Python CLI takes a Google Scholar user ID and scrapes citation data for all associated papers. For each paper, it collects the number of citations received per year.

**Input:** Google Scholar user ID (e.g., `RIi-1pAAAAAJ` from a profile URL like `scholar.google.com/citations?user=RIi-1pAAAAAJ`)

**Output:** JSON file containing papers and their yearly citation counts

## Visualization

The D3.js frontend reads the JSON index and renders interactive charts showing citation trends over time. Designed to be hosted as a GitHub Pages site.

## Data Format

```json
{
  "user_id": "RIi-1pAAAAAJ",
  "papers": [
    {
      "title": "Paper Title",
      "citations_by_year": {
        "2020": 10,
        "2021": 25,
        "2022": 42
      }
    }
  ]
}
```
