#!/usr/bin/env bash
set -euo pipefail

: "${GITHUB_TOKEN:?GITHUB_TOKEN environment variable is required}"

REPO_DIR="/tmp/repo"
rm -rf "$REPO_DIR"

git clone --depth 1 https://github.com/cfsima/criterionclosetpickspicks.git "$REPO_DIR"
cd "$REPO_DIR"

python3 src/generate_closet_picks_search.py

git config user.name "nas-scraper[bot]"
git config user.email "nas-scraper[bot]@users.noreply.github.com"
git add docs/closet_picks.csv scrape_state.json

if ! git diff --quiet || ! git diff --staged --quiet; then
  git commit -m "Update closet picks data"
  git push "https://x-access-token:${GITHUB_TOKEN}@github.com/cfsima/criterionclosetpickspicks.git" HEAD:main
else
  echo "No changes to commit."
fi
