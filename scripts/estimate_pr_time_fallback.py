#!/usr/bin/env python3
"""
Fallback script to estimate PR time using existing data when GitHub API access is limited.
Uses the methodology from calculate-time.md but with simplified estimates based on PR metadata.
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List
import re

# Time estimation configuration based on PR patterns
DEFAULT_DEV_HOURS = {
    "Feature": {"Small": 12, "Medium": 20, "Large": 32},
    "Bug_Fix": {"Small": 4, "Medium": 8, "Large": 12},
    "Enhancement": {"Small": 6, "Medium": 10, "Large": 16},
    "Infrastructure": {"Small": 4, "Medium": 8, "Large": 16},
    "Refactoring": {"Small": 8, "Medium": 12, "Large": 20},
    "Testing": {"Small": 6, "Medium": 12, "Large": 24},
    "UI_Enhancement": {"Small": 4, "Medium": 8, "Large": 12},
    "Documentation": {"Small": 2, "Medium": 4, "Large": 8},
    "Security": {"Small": 4, "Medium": 8, "Large": 12},
    "Performance": {"Small": 6, "Medium": 10, "Large": 16},
    "Database": {"Small": 6, "Medium": 10, "Large": 16},
    "Maintenance": {"Small": 3, "Medium": 5, "Large": 8},
    "Hotfix": {"Small": 4, "Medium": 6, "Large": 10},
    "Development": {"Small": 6, "Medium": 10, "Large": 16},
}

# Simulated PR body templates based on common patterns
PR_BODY_TEMPLATES = {
    "Feature": """## Summary
This PR implements {feature_description} functionality.

## Changes
- Added new components for {feature}
- Implemented business logic
- Added unit tests
- Updated documentation

## Testing
- Manual testing completed
- Unit tests passing
- Integration tests updated

## Related Issues
Closes #{issue_number}""",
    
    "Bug_Fix": """## Summary
This PR fixes {bug_description}.

## Root Cause
The issue was caused by {root_cause}.

## Solution
{solution_description}

## Testing
- Verified fix resolves the issue
- Added regression tests
- Tested edge cases

Fixes #{issue_number}""",
    
    "Enhancement": """## Summary
This PR enhances {component} with {enhancement_description}.

## Improvements
- Improved performance
- Better user experience
- Code optimization

## Testing
- Performance benchmarks show improvement
- User acceptance testing completed""",
    
    "Infrastructure": """## Summary
Infrastructure updates for {infrastructure_component}.

## Changes
- Updated deployment configurations
- Improved CI/CD pipeline
- Environment configuration changes

## Impact
- No breaking changes
- Improved deployment reliability""",
    
    "Default": """## Summary
{title}

## Changes
- Implementation details based on requirements
- Code changes as per specifications

## Testing
- Tests updated and passing
- Manual verification completed"""
}


def extract_issue_number(title: str) -> str:
    """Extract issue number from PR title"""
    match = re.search(r'#?(\d+)', title)
    return match.group(1) if match else "N/A"


def generate_simulated_pr_body(pr: Dict) -> str:
    """Generate a simulated PR body based on PR metadata"""
    category = pr.get("category", "Default")
    title = pr.get("title", "")
    
    template = PR_BODY_TEMPLATES.get(category, PR_BODY_TEMPLATES["Default"])
    
    # Extract information from title
    issue_number = extract_issue_number(title)
    
    # Clean up title for description
    description = re.sub(r'^\d+\s*', '', title)  # Remove leading numbers
    description = re.sub(r'^#\d+\s*', '', description)  # Remove issue references
    description = description.lower().replace('_', ' ').replace('-', ' ')
    
    # Fill in template placeholders
    replacements = {
        "{feature_description}": description,
        "{feature}": description.split()[0] if description else "feature",
        "{bug_description}": description,
        "{root_cause}": "incorrect state handling",
        "{solution_description}": f"Updated logic to properly handle {description}",
        "{component}": description.split()[0] if description else "component",
        "{enhancement_description}": description,
        "{infrastructure_component}": description,
        "{title}": title,
        "{issue_number}": issue_number
    }
    
    body = template
    for placeholder, value in replacements.items():
        body = body.replace(placeholder, value)
    
    return body


def estimate_time_from_metadata(pr: Dict) -> Dict:
    """
    Estimate time based on PR metadata when commit data is not available.
    Uses category and complexity to determine estimates.
    """
    category = pr.get("category", "Maintenance")
    complexity = pr.get("complexity", "Small")
    
    # Get base hours from lookup table
    base_hours = DEFAULT_DEV_HOURS.get(category, DEFAULT_DEV_HOURS["Maintenance"]).get(complexity, 6)
    
    # Adjust based on title indicators
    title = pr.get("title", "").lower()
    
    # Adjustment factors
    multiplier = 1.0
    
    if "refactor" in title or "restructure" in title:
        multiplier *= 1.2
    if "test" in title or "testing" in title:
        multiplier *= 1.1
    if "fix" in title and "hotfix" not in title:
        multiplier *= 0.9
    if "update" in title or "enhance" in title:
        multiplier *= 1.1
    if "mvp" in title:
        multiplier *= 1.3
    if "working" in title or "mid" in title:
        multiplier *= 0.7  # Quick changes
    
    estimated_hours = round(base_hours * multiplier, 1)
    
    # Estimate sessions based on complexity
    sessions = {"Small": 1, "Medium": 2, "Large": 3}.get(complexity, 1)
    
    # Estimate commits based on hours (roughly 1 commit per 2 hours of work)
    estimated_commits = max(1, round(estimated_hours / 2))
    
    return {
        "estimated_hours": estimated_hours,
        "sessions": sessions,
        "commits": estimated_commits,
        "method": "metadata_based",
        "confidence": "low"  # Since we don't have actual commit data
    }


def process_pr_data_fallback():
    """Process PR data using fallback estimation when GitHub API is not accessible"""
    
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
    
    # Process each PR
    enhanced_prs = []
    total_prs = len(data["pull_requests"])
    
    print(f"Processing {total_prs} pull requests using fallback estimation...")
    print("Note: Using metadata-based estimation since GitHub API access is limited.\n")
    
    total_github_estimated = 0
    total_sessions = 0
    total_commits = 0
    
    for i, pr in enumerate(data["pull_requests"], 1):
        pr_number = pr["pr_number"]
        
        if i % 50 == 0:
            print(f"Processing... {i}/{total_prs} PRs completed")
        
        # Copy original PR data
        enhanced_pr = pr.copy()
        
        # Generate simulated PR body based on metadata
        enhanced_pr["pr_body"] = generate_simulated_pr_body(pr)
        enhanced_pr["pr_body_source"] = "simulated"
        
        # Estimate time based on metadata
        time_estimate = estimate_time_from_metadata(pr)
        enhanced_pr["github_estimate"] = time_estimate
        
        # Track totals
        total_github_estimated += time_estimate["estimated_hours"]
        total_sessions += time_estimate["sessions"]
        total_commits += time_estimate["commits"]
        
        # Compare with existing estimate
        existing_dev_hours = pr.get("dev_hours", 0)
        enhanced_pr["estimate_comparison"] = {
            "existing_dev_hours": existing_dev_hours,
            "metadata_estimated_hours": time_estimate["estimated_hours"],
            "difference": round(time_estimate["estimated_hours"] - existing_dev_hours, 1),
            "percentage_diff": round(
                ((time_estimate["estimated_hours"] - existing_dev_hours) / existing_dev_hours * 100) 
                if existing_dev_hours > 0 else 0, 1
            )
        }
        
        enhanced_prs.append(enhanced_pr)
    
    print(f"Processed all {total_prs} PRs")
    
    # Create enhanced output
    output_data = {
        "repository": data.get("repository"),
        "target_branch": data.get("target_branch"),
        "analysis_date": datetime.now().strftime("%Y-%m-%d"),
        "original_analysis_date": data.get("analysis_date"),
        "total_prs": total_prs,
        "estimation_method": "fallback_metadata_based",
        "note": "Estimates based on PR metadata due to limited GitHub API access",
        "summary": data.get("summary"),
        "metadata_estimation_summary": {
            "total_metadata_estimated_hours": round(total_github_estimated, 1),
            "total_original_dev_hours": data["summary"]["total_estimated_dev_hours"],
            "difference_hours": round(total_github_estimated - data["summary"]["total_estimated_dev_hours"], 1),
            "percentage_difference": round(
                ((total_github_estimated - data["summary"]["total_estimated_dev_hours"]) / 
                 data["summary"]["total_estimated_dev_hours"] * 100), 1
            ),
            "average_sessions_per_pr": round(total_sessions / total_prs, 1) if total_prs > 0 else 0,
            "average_commits_per_pr": round(total_commits / total_prs, 1) if total_prs > 0 else 0,
            "confidence_level": "low - based on patterns not actual commit data"
        },
        "estimation_config": {
            "method": "Metadata-based estimation using category, complexity, and title patterns",
            "categories_used": list(DEFAULT_DEV_HOURS.keys()),
            "complexities": ["Small", "Medium", "Large"],
            "note": "Actual commit-based estimation would be more accurate with GitHub API access"
        },
        "pull_requests": enhanced_prs,
        "methodology": data.get("methodology"),
        "fallback_methodology": {
            "description": "Since GitHub API access is limited, estimates are based on:",
            "factors": [
                "PR category (Feature, Bug_Fix, etc.)",
                "Complexity (Small, Medium, Large)",
                "Title keywords (refactor, test, fix, enhance, etc.)",
                "Historical patterns from similar PRs"
            ],
            "limitations": [
                "No actual commit timing data",
                "Cannot account for actual work sessions",
                "PR bodies are simulated based on templates",
                "Estimates may vary from actual time spent"
            ]
        }
    }
    
    # Write output file
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2, default=str)
    
    print(f"\n✅ Completed! Enhanced data written to {output_file}")
    print(f"\n📊 Summary:")
    print(f"   Total PRs processed: {total_prs}")
    print(f"   Metadata estimated hours: {round(total_github_estimated, 1)}")
    print(f"   Original estimated dev hours: {data['summary']['total_estimated_dev_hours']}")
    print(f"   Difference: {round(total_github_estimated - data['summary']['total_estimated_dev_hours'], 1)} hours")
    print(f"\n⚠️  Note: These are fallback estimates. For more accurate results,")
    print(f"   ensure your GitHub token has access to the repository.")


if __name__ == "__main__":
    print("=" * 60)
    print("PR Time Estimation Tool (Fallback Mode)")
    print("=" * 60)
    process_pr_data_fallback()