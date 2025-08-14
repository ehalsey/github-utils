#!/usr/bin/env python3
"""Fetch closed GitHub issues with time estimation between two dates.

This script queries the GitHub Search API for issues that were closed within
an inclusive date range and estimates the time taken to resolve each issue.
Time calculations use business hours (7am-7pm PST, Mon-Fri).
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Dict, Any
from datetime import datetime, timedelta
import pytz
import requests
import json


def get_pst_timezone():
    """Get PST/PDT timezone."""
    return pytz.timezone('America/Los_Angeles')


def parse_github_datetime(date_str: str) -> datetime:
    """Parse GitHub's ISO 8601 datetime string."""
    if not date_str:
        return None
    # GitHub uses UTC timezone in their API
    dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    # Convert to PST/PDT
    pst = get_pst_timezone()
    return dt.astimezone(pst)


def is_business_day(dt: datetime) -> bool:
    """Check if datetime falls on a business day (Mon-Fri)."""
    return dt.weekday() < 5  # Monday = 0, Friday = 4


def get_business_hours_in_day(dt: datetime) -> tuple[datetime, datetime]:
    """Get business hours (7am-7pm) for a given day, or extended if work detected."""
    start = dt.replace(hour=7, minute=0, second=0, microsecond=0)
    end = dt.replace(hour=19, minute=0, second=0, microsecond=0)  # 7pm
    
    # If the actual time is after 7pm, extend to midnight
    if dt.hour >= 19:
        end = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
    
    return start, end


def calculate_business_hours(start_dt: datetime, end_dt: datetime) -> float:
    """Calculate business hours between two datetimes.
    
    Rules:
    - Business hours: 7am-7pm PST Mon-Fri
    - If work detected after 7pm, count until midnight
    - Skip weekends unless activity detected
    """
    if not start_dt or not end_dt:
        return 0.0
    
    if start_dt > end_dt:
        start_dt, end_dt = end_dt, start_dt
    
    total_hours = 0.0
    current_dt = start_dt
    
    while current_dt.date() <= end_dt.date():
        if is_business_day(current_dt):
            biz_start, biz_end = get_business_hours_in_day(current_dt)
            
            # Determine the actual start and end times for this day
            day_start = max(current_dt, biz_start) if current_dt.date() == start_dt.date() else biz_start
            day_end = min(end_dt, biz_end) if current_dt.date() == end_dt.date() else biz_end
            
            # Calculate hours for this day
            if day_start < day_end:
                hours = (day_end - day_start).total_seconds() / 3600
                total_hours += hours
        else:
            # Weekend - check if there's activity
            # For now, if issue was opened or closed on weekend, count some hours
            if current_dt.date() == start_dt.date() or current_dt.date() == end_dt.date():
                # Count 4 hours for weekend work
                total_hours += 4.0
        
        current_dt = (current_dt + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    
    return total_hours


def fetch_issue_timeline(repo: str, issue_number: int, token: str | None = None) -> List[Dict[str, Any]]:
    """Fetch timeline events for a specific issue."""
    owner, repo_name = repo.split('/')
    url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}/timeline"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    events = []
    page = 1
    per_page = 100
    
    while True:
        params = {"per_page": per_page, "page": page}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in [403, 404]:
            # Timeline API might not be available or forbidden, return empty
            return []
        response.raise_for_status()
        
        data = response.json()
        if not data:
            break
        events.extend(data)
        if len(data) < per_page:
            break
        page += 1
    
    return events


def fetch_issue_events(repo: str, issue_number: int, token: str | None = None) -> List[Dict[str, Any]]:
    """Fetch events for a specific issue."""
    owner, repo_name = repo.split('/')
    url = f"https://api.github.com/repos/{owner}/{repo_name}/issues/{issue_number}/events"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    events = []
    page = 1
    per_page = 100
    
    while True:
        params = {"per_page": per_page, "page": page}
        response = requests.get(url, headers=headers, params=params, timeout=30)
        if response.status_code in [403, 404]:
            # Events API might not be available or forbidden, return empty
            return []
        response.raise_for_status()
        
        data = response.json()
        if not data:
            break
        events.extend(data)
        if len(data) < per_page:
            break
        page += 1
    
    return events


def analyze_issue_timing(issue: Dict[str, Any], repo: str, token: str | None = None) -> Dict[str, Any]:
    """Analyze timing information for an issue."""
    created_at = parse_github_datetime(issue.get('created_at'))
    closed_at = parse_github_datetime(issue.get('closed_at'))
    
    # Fetch timeline events for more detailed analysis
    timeline = fetch_issue_timeline(repo, issue['number'], token)
    events = fetch_issue_events(repo, issue['number'], token) if not timeline else []
    
    # Calculate business hours
    business_hours = calculate_business_hours(created_at, closed_at)
    
    # Calculate calendar days
    calendar_days = (closed_at - created_at).days if created_at and closed_at else 0
    
    # Find key events
    first_response = None
    assigned_at = None
    labeled_at = None
    
    all_events = timeline + events
    for event in all_events:
        event_type = event.get('event', event.get('type'))
        event_time = parse_github_datetime(event.get('created_at'))
        
        if event_type in ['commented', 'comment'] and not first_response:
            # Skip if it's the issue author commenting
            if event.get('actor', {}).get('login') != issue.get('user', {}).get('login'):
                first_response = event_time
        
        if event_type == 'assigned' and not assigned_at:
            assigned_at = event_time
        
        if event_type == 'labeled' and not labeled_at:
            labeled_at = event_time
    
    # Calculate time to first response
    time_to_first_response = None
    if first_response:
        time_to_first_response = calculate_business_hours(created_at, first_response)
    
    # Calculate time to assignment
    time_to_assignment = None
    if assigned_at:
        time_to_assignment = calculate_business_hours(created_at, assigned_at)
    
    return {
        'number': issue['number'],
        'title': issue['title'],
        'created_at': created_at.isoformat() if created_at else None,
        'closed_at': closed_at.isoformat() if closed_at else None,
        'assignee': issue.get('assignee', {}).get('login') if issue.get('assignee') else None,
        'labels': [label['name'] for label in issue.get('labels', [])],
        'business_hours': round(business_hours, 2),
        'calendar_days': calendar_days,
        'time_to_first_response_hours': round(time_to_first_response, 2) if time_to_first_response else None,
        'time_to_assignment_hours': round(time_to_assignment, 2) if time_to_assignment else None,
        'url': issue['html_url']
    }


def fetch_closed_issues(repo: str, start_date: str, end_date: str, token: str | None = None) -> List[Dict[str, Any]]:
    """Return closed issues for repo between start_date and end_date."""
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
    parser = argparse.ArgumentParser(
        description="Fetch closed GitHub issues with time estimation between two dates."
    )
    parser.add_argument("repo", help="Repository in the form owner/name")
    parser.add_argument("start", help="Start date YYYY-MM-DD")
    parser.add_argument("end", help="End date YYYY-MM-DD")
    parser.add_argument("--out", help="Optional output file to write JSON results")
    parser.add_argument("--csv", help="Optional CSV output file for analysis")
    parser.add_argument("--detailed", action="store_true", 
                       help="Fetch detailed timeline data (slower but more accurate)")
    
    args = parser.parse_args(argv)
    
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("Warning: GITHUB_TOKEN not set. API rate limits will apply.", file=sys.stderr)
    
    print(f"Fetching closed issues from {args.repo} between {args.start} and {args.end}...", file=sys.stderr)
    issues = fetch_closed_issues(args.repo, args.start, args.end, token)
    print(f"Found {len(issues)} closed issues. Analyzing timing...", file=sys.stderr)
    
    # Analyze timing for each issue
    analyzed_issues = []
    for i, issue in enumerate(issues):
        print(f"Analyzing issue #{issue['number']} ({i+1}/{len(issues)})...", file=sys.stderr)
        if args.detailed:
            analysis = analyze_issue_timing(issue, args.repo, token)
        else:
            # Simple analysis without fetching timeline
            created_at = parse_github_datetime(issue.get('created_at'))
            closed_at = parse_github_datetime(issue.get('closed_at'))
            business_hours = calculate_business_hours(created_at, closed_at)
            calendar_days = (closed_at - created_at).days if created_at and closed_at else 0
            
            analysis = {
                'number': issue['number'],
                'title': issue['title'],
                'created_at': created_at.isoformat() if created_at else None,
                'closed_at': closed_at.isoformat() if closed_at else None,
                'assignee': issue.get('assignee', {}).get('login') if issue.get('assignee') else None,
                'labels': [label['name'] for label in issue.get('labels', [])],
                'business_hours': round(business_hours, 2),
                'calendar_days': calendar_days,
                'url': issue['html_url']
            }
        analyzed_issues.append(analysis)
    
    # Calculate summary statistics
    total_hours = sum(i['business_hours'] for i in analyzed_issues)
    avg_hours = total_hours / len(analyzed_issues) if analyzed_issues else 0
    max_hours = max((i['business_hours'] for i in analyzed_issues), default=0)
    min_hours = min((i['business_hours'] for i in analyzed_issues), default=0)
    
    summary = {
        'total_issues': len(analyzed_issues),
        'total_business_hours': round(total_hours, 2),
        'average_business_hours': round(avg_hours, 2),
        'max_business_hours': round(max_hours, 2),
        'min_business_hours': round(min_hours, 2),
        'issues': analyzed_issues
    }
    
    # Output results
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print(f"Results written to {args.out}", file=sys.stderr)
    
    if args.csv:
        import csv
        with open(args.csv, "w", newline='', encoding="utf-8") as csvfile:
            if analyzed_issues:
                fieldnames = ['number', 'title', 'assignee', 'business_hours', 'calendar_days', 
                             'created_at', 'closed_at', 'labels', 'url']
                if args.detailed:
                    fieldnames.extend(['time_to_first_response_hours', 'time_to_assignment_hours'])
                
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                for issue in analyzed_issues:
                    row = {k: issue.get(k, '') for k in fieldnames}
                    # Convert labels list to string
                    if 'labels' in row:
                        row['labels'] = ', '.join(row['labels']) if row['labels'] else ''
                    writer.writerow(row)
        print(f"CSV results written to {args.csv}", file=sys.stderr)
    
    # Print summary to stdout
    print("\n=== Summary ===")
    print(f"Total issues: {summary['total_issues']}")
    print(f"Total business hours: {summary['total_business_hours']}")
    print(f"Average resolution time: {summary['average_business_hours']} hours")
    print(f"Fastest resolution: {summary['min_business_hours']} hours")
    print(f"Slowest resolution: {summary['max_business_hours']} hours")
    
    if not args.out:
        print("\n=== Top 10 Issues by Time ===")
        sorted_issues = sorted(analyzed_issues, key=lambda x: x['business_hours'], reverse=True)[:10]
        for issue in sorted_issues:
            print(f"#{issue['number']}: {issue['business_hours']} hours - {issue['title'][:60]}...")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())