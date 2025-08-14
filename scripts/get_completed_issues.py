#!/usr/bin/env python3
"""Fetch closed GitHub issues between two dates.

This script queries the GitHub Search API for issues that were closed within
an inclusive date range. A personal access token can be supplied via the
``GITHUB_TOKEN`` environment variable to increase the rate limit.
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Dict, Any

import requests


def fetch_closed_issues(repo: str, start_date: str, end_date: str, token: str | None = None) -> List[Dict[str, Any]]:
    """Return closed issues for ``repo`` between ``start_date`` and ``end_date``.

    Parameters
    ----------
    repo: ``str``
        The repository in ``owner/name`` form.
    start_date: ``str``
        ISO-8601 start date (YYYY-MM-DD).
    end_date: ``str``
        ISO-8601 end date (YYYY-MM-DD).
    token: ``str | None``
        Optional GitHub personal access token for authenticated requests.
    """
    url = "https://api.github.com/search/issues"
    query = f"repo:{repo} is:issue state:closed closed:{start_date}..{end_date}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    issues: List[Dict[str, Any]] = []
    page = 1
    per_page = 100
    while True:
        params = {"q": query, "per_page": per_page, "page": page}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        items = data.get("items", [])
        issues.extend(items)
        if len(items) < per_page:
            break
        page += 1
    return issues


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch closed GitHub issues between two dates.")
    parser.add_argument("repo", help="Repository in the form owner/name")
    parser.add_argument("start", help="Start date YYYY-MM-DD")
    parser.add_argument("end", help="End date YYYY-MM-DD")
    parser.add_argument("--out", help="Optional output file to write JSON results")

    args = parser.parse_args(argv)

    token = os.environ.get("GITHUB_TOKEN")
    issues = fetch_closed_issues(args.repo, args.start, args.end, token)

    if args.out:
        import json
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(issues, fh, indent=2)
    else:
        for issue in issues:
            closed_at = issue.get("closed_at", "?")
            title = issue.get("title", "")
            number = issue.get("number")
            print(f"#{number} {closed_at} {title}")

    return 0

# /workspaces/github-utils/scripts $ export GITHUB_TOKEN=ghp_5... && python get_completed_issues.py Precision-Medical-Group/patient-scheduling-solution 2025-06-01 2025-07-31 --out /workspaces/output/results.json


if __name__ == "__main__":  # pragma: no cover - script entry point
    sys.exit(main())
