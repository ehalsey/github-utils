#!/usr/bin/env python3
"""
Script to fetch PR bodies from GitHub and estimate time based on commit patterns.
Reads from output/prs-to-date.json and outputs enhanced data to output/prs-with-estimates.json
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional
import requests
from time import sleep

# GitHub API configuration
GITHUB_API_BASE = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Time estimation configuration (based on calculate-time.md)
MAX_COMMIT_DIFF_MINUTES = 120  # If commits are within 2 hours, they're part of same session
FIRST_COMMIT_BUFFER_MINUTES = 120  # Add 2 hours to account for work before first commit


def get_github_headers():
    """Get headers for GitHub API requests"""
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PR-Time-Estimator"
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"token {GITHUB_TOKEN}"
    return headers


def fetch_pr_body(owner: str, repo: str, pr_number: int) -> Optional[str]:
    """Fetch PR body from GitHub API"""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = get_github_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data.get("body", "")
    except requests.exceptions.RequestException as e:
        print(f"Error fetching PR #{pr_number}: {e}")
        return None


def fetch_pr_commits(owner: str, repo: str, pr_number: int) -> List[Dict]:
    """Fetch commits for a PR from GitHub API"""
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
    headers = get_github_headers()
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        commits = response.json()
        
        # Extract timestamp and author info
        commit_data = []
        for commit in commits:
            commit_data.append({
                "sha": commit["sha"],
                "timestamp": datetime.fromisoformat(
                    commit["commit"]["author"]["date"].replace("Z", "+00:00")
                ),
                "author": commit["commit"]["author"]["name"],
                "message": commit["commit"]["message"]
            })
        return commit_data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching commits for PR #{pr_number}: {e}")
        return []


def estimate_time_from_commits(commits: List[Dict]) -> Dict[str, float]:
    """
    Estimate development time based on commit patterns.
    Uses the session-based algorithm described in calculate-time.md
    """
    if not commits:
        return {"estimated_hours": 0, "sessions": 0, "commits": 0}
    
    # Sort commits by timestamp
    commits.sort(key=lambda c: c["timestamp"])
    
    total_minutes = 0
    sessions = 1
    
    # Add buffer for work before first commit
    total_minutes += FIRST_COMMIT_BUFFER_MINUTES
    
    # Process commits to identify sessions
    for i in range(1, len(commits)):
        diff_minutes = (commits[i]["timestamp"] - commits[i-1]["timestamp"]).total_seconds() / 60
        
        if diff_minutes <= MAX_COMMIT_DIFF_MINUTES:
            # Same session - add the time diff
            total_minutes += diff_minutes
        else:
            # New session - add buffer for new session
            sessions += 1
            total_minutes += FIRST_COMMIT_BUFFER_MINUTES
    
    return {
        "estimated_hours": round(total_minutes / 60, 1),
        "sessions": sessions,
        "commits": len(commits)
    }


def process_pr_data():
    """Main function to process PR data and add estimates"""
    
    # Read input file
    input_file = "/workspaces/github-utils/output/prs-to-date.json"
    output_file = "/workspaces/github-utils/output/prs-with-estimates.json"
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}")
        sys.exit(1)
    
    # Extract owner and repo from the data
    repo_name = data.get("repository", "patient-scheduling-solution")
    # Assuming the repo is under a specific owner - you may need to adjust this
    owner = "your-github-org"  # Replace with actual owner
    
    # Check if owner is provided via environment variable
    owner = os.environ.get("GITHUB_OWNER", owner)
    
    if owner == "your-github-org":
        print("Warning: Using default owner 'your-github-org'. Set GITHUB_OWNER environment variable.")
    
    # Process each PR
    enhanced_prs = []
    total_processed = 0
    total_prs = len(data["pull_requests"])
    
    print(f"Processing {total_prs} pull requests...")
    
    for pr in data["pull_requests"]:
        pr_number = pr["pr_number"]
        total_processed += 1
        
        print(f"Processing PR #{pr_number} ({total_processed}/{total_prs})...")
        
        # Copy original PR data
        enhanced_pr = pr.copy()
        
        # Fetch PR body
        pr_body = fetch_pr_body(owner, repo_name, pr_number)
        enhanced_pr["pr_body"] = pr_body if pr_body else ""
        
        # Fetch commits and estimate time
        commits = fetch_pr_commits(owner, repo_name, pr_number)
        
        if commits:
            time_estimate = estimate_time_from_commits(commits)
            enhanced_pr["github_estimate"] = time_estimate
            
            # Compare with existing estimate
            existing_dev_hours = pr.get("dev_hours", 0)
            enhanced_pr["estimate_comparison"] = {
                "existing_dev_hours": existing_dev_hours,
                "github_estimated_hours": time_estimate["estimated_hours"],
                "difference": round(time_estimate["estimated_hours"] - existing_dev_hours, 1)
            }
        else:
            enhanced_pr["github_estimate"] = {
                "estimated_hours": 0,
                "sessions": 0,
                "commits": 0,
                "note": "No commit data available"
            }
            enhanced_pr["estimate_comparison"] = {
                "existing_dev_hours": pr.get("dev_hours", 0),
                "github_estimated_hours": 0,
                "difference": 0
            }
        
        enhanced_prs.append(enhanced_pr)
        
        # Rate limiting - be nice to GitHub API
        if not GITHUB_TOKEN:
            sleep(1)  # Slower rate without auth
        else:
            sleep(0.1)  # Faster with auth
    
    # Create enhanced output
    output_data = {
        "repository": data.get("repository"),
        "target_branch": data.get("target_branch"),
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "original_analysis_date": data.get("analysis_date"),
        "total_prs": total_prs,
        "summary": data.get("summary"),
        "github_estimation_summary": {
            "total_github_estimated_hours": sum(pr["github_estimate"]["estimated_hours"] for pr in enhanced_prs),
            "total_original_dev_hours": data["summary"]["total_estimated_dev_hours"],
            "average_sessions_per_pr": round(
                sum(pr["github_estimate"]["sessions"] for pr in enhanced_prs) / total_prs, 1
            ) if total_prs > 0 else 0,
            "average_commits_per_pr": round(
                sum(pr["github_estimate"]["commits"] for pr in enhanced_prs) / total_prs, 1
            ) if total_prs > 0 else 0
        },
        "estimation_config": {
            "max_commit_diff_minutes": MAX_COMMIT_DIFF_MINUTES,
            "first_commit_buffer_minutes": FIRST_COMMIT_BUFFER_MINUTES,
            "method": "Commit session analysis as per calculate-time.md"
        },
        "pull_requests": enhanced_prs,
        "methodology": data.get("methodology")
    }
    
    # Write output file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\nCompleted! Enhanced data written to {output_file}")
    print(f"Total GitHub estimated hours: {output_data['github_estimation_summary']['total_github_estimated_hours']:.1f}")
    print(f"Original estimated dev hours: {output_data['github_estimation_summary']['total_original_dev_hours']}")


if __name__ == "__main__":
    if not GITHUB_TOKEN:
        print("Warning: GITHUB_TOKEN not set. API rate limits will be restrictive.")
        print("Set it with: export GITHUB_TOKEN=your_github_token")
    
    owner = os.environ.get("GITHUB_OWNER")
    if not owner:
        print("\nError: GITHUB_OWNER environment variable must be set.")
        print("Set it with: export GITHUB_OWNER=your-github-org")
        sys.exit(1)
    
    process_pr_data()