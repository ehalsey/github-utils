To determine the amount of time spent developing and testing code for a list of pull requests (PRs) using only GitHub data such as issues, commits, PRs, and related elements (e.g., timestamps, commit histories), note that GitHub does not natively track actual hours worked. There is no built-in time-tracking feature, so any determination must rely on inferences and estimations from available metadata. The most common and substantiated approach involves analyzing commit timestamps to estimate "active" coding sessions, treating development and testing as intertwined activities (since commits often include both code changes and test updates without clear separation). This method uses heuristics to approximate effort based on commit patterns, as direct measurement isn't possible.

### Key Assumptions and Limitations
- **Assumptions**: Commits reflect periods of active work. Consecutive commits close in time indicate continuous sessions of development/testing. Gaps suggest breaks. Testing is typically embedded in the commit history (e.g., via commits updating test files or messages like "fix tests"), so it's not easily isolated without additional heuristics.
- **Limitations**: This yields an estimate, not precise hours (e.g., it ignores non-commit activities like debugging, reading docs, or local testing without commits). Calendar time (e.g., weekends, holidays) isn't deducted. It's unsuitable for billing or performance reviews without validation. If PRs span multiple developers, aggregate per author. External factors like rebases or squashed commits can skew data.

### Step-by-Step Method
You can implement this manually via the GitHub UI/API, or script it using the GitHub API (e.g., in Python with libraries like PyGitHub or requests). For a list of PRs, process each one individually and sum totals if needed. The core algorithm is based on grouping commits into sessions, a technique popularized by tools like git-hours and git-dev-time. Here's how:

1. **Gather Data for Each PR**:
   - Use the GitHub API endpoint `/repos/{owner}/{repo}/pulls/{pr_number}/commits` to fetch all commits in the PR (or view them in the GitHub UI under the "Commits" tab).
   - Extract each commit's timestamp (use the "author date" for when the work was done, not "commit date" which might reflect rebases).
   - Sort commits chronologically by timestamp.
   - Optionally, link to related issues (via PR descriptions or "closes #issue" keywords) to check for time-related comments, but this rarely provides quantitative data.

2. **Apply the Commit Session Estimation Algorithm**:
   - Define configurable thresholds (based on common practices):
     - Max commit diff: 2-3 hours (e.g., 120-180 minutes). If two commits are within this window, they're part of the same session.
     - First-commit buffer: Add 1-2 hours per session to account for untracked work before the first commit (e.g., planning or initial coding).
   - For the sorted commits:
     - Initialize total time = 0.
     - Start with the first commit: Begin a new session and add the first-commit buffer.
     - For each subsequent commit:
       - Calculate diff = current timestamp - previous timestamp.
       - If diff ≤ max commit diff, add diff to the current session's time.
       - If diff > max commit diff, end the current session, add its time to total, and start a new session (adding the first-commit buffer again).
     - After processing all, add the final session's time.
   - This gives an estimated hours for the PR's commits, representing development and testing time combined.
   - Example pseudocode (executable via the code_execution tool if needed for verification):
     ```
     import datetime

     def estimate_time(commits, max_diff_minutes=120, first_buffer_minutes=120):
         if not commits:
             return 0
         commits.sort(key=lambda c: c['timestamp'])  # Assume commits is list of dicts with 'timestamp' as datetime
         total_minutes = 0
         session_start = commits[0]['timestamp']
         total_minutes += first_buffer_minutes
         for i in range(1, len(commits)):
             diff = (commits[i]['timestamp'] - commits[i-1]['timestamp']).total_seconds() / 60
             if diff <= max_diff_minutes:
                 total_minutes += diff
             else:
                 # End session, start new
                 total_minutes += first_buffer_minutes
                 session_start = commits[i]['timestamp']
         return total_minutes / 60  # Convert to hours
     ```

3. **Handle Testing Specifically (If Separation is Desired)**:
   - Testing time is challenging to isolate, as it's often interleaved. To approximate:
     - Filter commits that modify test files (e.g., via commit diffs showing changes in paths like `/tests/`, `/spec/`, or files ending in `_test.py`). Use the API endpoint `/repos/{owner}/{repo}/commits/{sha}` to get file changes per commit.
     - Apply the same algorithm only to these "test-related" commits for a subset estimate.
     - Alternatively, if the repo uses GitHub Actions for CI/CD testing, fetch workflow run durations via `/repos/{owner}/{repo}/actions/runs` (this measures automated test execution time, not developer manual testing time).
   - If issues linked to the PR mention testing (e.g., "tested locally"), this adds qualitative context but no quantifiable time.

4. **Aggregate for the List of PRs**:
   - Sum estimated hours across all PRs for a total.
   - Subtract overlaps if PRs share commits (rare, but check via commit SHAs).
   - Use tables for presentation if analyzing multiple PRs:

     | PR Number | First Commit Date | Last Commit Date | Estimated Hours (Dev + Test) | Notes |
     |-----------|-------------------|------------------|------------------------------|-------|
     | #123     | 2025-08-01       | 2025-08-05      | 12.5                        | Includes 3 test commits |
     | #456     | 2025-08-03       | 2025-08-04      | 8.0                         | Heavy on testing files |
     | Total    | -                | -               | 20.5                        | -     |

5. **Refinements and Alternatives**:
   - **Incorporate Issues/PR Metadata**: Check PR creation-to-merge time (via API fields `created_at` and `merged_at`) as "lead time," but subtract review/waiting periods (e.g., from review request timestamps). This is calendar time, not effort.
   - **Per-Author Breakdown**: Group by commit author for multi-contributor PRs.
   - **Validation**: Cross-check with PR size (lines changed) or commit count, but these correlate loosely with time.
   - If no commits (e.g., empty PRs), fall back to PR open duration or issue timelines.

This method provides a reasonable proxy using only GitHub data, but for more accuracy, integrate external time-tracking tools (though that's outside the question's scope). If scripting, test with sample data via GitHub's API rate limits.