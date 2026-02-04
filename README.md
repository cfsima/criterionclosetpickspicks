# Criterion Closet Picks Picks

A tool to aggregate and analyze picks from the [Criterion Closet](https://www.criterion.com/closet-picks).

## Deployed Site

View the aggregated data and statistics here: **[CriterionClosetPicksPicks](https://cfsima.github.io/criterionclosetpickspicks/)**

## Overview

This project scrapes the Criterion Closet Picks website to gather data on which movies are picked most often by visiting guests. The data is updated weekly via GitHub Actions.

## Usage

### Prerequisites

- Python 3.x
- Playwright

### Running the Scraper

1.  Install dependencies:
    ```bash
    pip install playwright
    playwright install chromium
    ```

2.  Run the script:
    ```bash
    python src/generate_closet_picks.py
    ```

The data will be saved to `docs/closet_picks.csv`.
