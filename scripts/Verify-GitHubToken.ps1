param(
    [Parameter(Mandatory=$true)]
    [string]$Token
)

Write-Host "Testing GitHub PAT for repository access..." -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# Test 1: Basic authentication
Write-Host "`n1. Testing basic authentication..." -ForegroundColor Yellow
$headers = @{
    "Authorization" = "token $Token"
}

try {
    $userResponse = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -Method Get
    Write-Host "✅ Token is valid" -ForegroundColor Green
    Write-Host "   Authenticated as: $($userResponse.login)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Token is invalid or expired" -ForegroundColor Red
    Write-Host "   Error: $_" -ForegroundColor Red
    exit 1
}

# Test 2: Repository access
Write-Host "`n2. Testing repository access..." -ForegroundColor Yellow
try {
    $repoResponse = Invoke-RestMethod -Uri "https://api.github.com/repos/Precision-Medical-Group/patient-scheduling-solution" -Headers $headers -Method Get
    Write-Host "✅ Can access the repository" -ForegroundColor Green
    Write-Host "   Repository is private: $($repoResponse.private)" -ForegroundColor Gray
    Write-Host "   Default branch: $($repoResponse.default_branch)" -ForegroundColor Gray
} catch {
    Write-Host "❌ Cannot access repository" -ForegroundColor Red
    Write-Host "   This could mean:" -ForegroundColor Yellow
    Write-Host "   - The token doesn't have 'repo' scope" -ForegroundColor Yellow
    Write-Host "   - You don't have access to this repository" -ForegroundColor Yellow
    Write-Host "   - The repository name/owner is incorrect" -ForegroundColor Yellow
}

# Test 3: Check token scopes
Write-Host "`n3. Checking token scopes..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "https://api.github.com/user" -Headers $headers -Method Head
    $scopes = $response.Headers["X-OAuth-Scopes"]
    if ($scopes) {
        Write-Host "✅ Token has the following scopes:" -ForegroundColor Green
        Write-Host "   $scopes" -ForegroundColor Gray
    } else {
        Write-Host "ℹ️  Cannot retrieve token scopes" -ForegroundColor Cyan
    }
} catch {
    Write-Host "ℹ️  Cannot retrieve token scopes" -ForegroundColor Cyan
}

# Test 4: Try to list issues
Write-Host "`n4. Testing issue access..." -ForegroundColor Yellow
try {
    $issuesResponse = Invoke-RestMethod -Uri "https://api.github.com/repos/Precision-Medical-Group/patient-scheduling-solution/issues?per_page=1" -Headers $headers -Method Get
    Write-Host "✅ Can read issues" -ForegroundColor Green
} catch {
    Write-Host "❌ Cannot read issues" -ForegroundColor Red
}

# Test 5: Test write access (check if can create issues)
Write-Host "`n5. Testing write access..." -ForegroundColor Yellow
try {
    # Try a dry-run by checking collaborator status
    $collabCheck = Invoke-WebRequest -Uri "https://api.github.com/repos/Precision-Medical-Group/patient-scheduling-solution/collaborators/$($userResponse.login)" -Headers $headers -Method Get -ErrorAction SilentlyContinue
    if ($collabCheck.StatusCode -eq 204) {
        Write-Host "✅ You have collaborator access" -ForegroundColor Green
    }
} catch {
    if ($_.Exception.Response.StatusCode -eq 404) {
        Write-Host "⚠️  You are not a direct collaborator (may have access through team)" -ForegroundColor Yellow
    } else {
        Write-Host "ℹ️  Cannot determine collaborator status" -ForegroundColor Cyan
    }
}

Write-Host "`n==========================================" -ForegroundColor Cyan
Write-Host "Summary:" -ForegroundColor Cyan
Write-Host "✅ Your token appears to be working!" -ForegroundColor Green
Write-Host ""
Write-Host "You can use this token for:" -ForegroundColor Yellow
Write-Host "- Git operations: git clone https://<TOKEN>@github.com/..." -ForegroundColor Gray
Write-Host "- GitHub CLI: echo <TOKEN> | gh auth login --with-token" -ForegroundColor Gray
Write-Host "- API calls: Use 'Authorization: token <TOKEN>' header" -ForegroundColor Gray
Write-Host ""
Write-Host "To configure git to use this token:" -ForegroundColor Yellow
Write-Host "git config --global url.'https://$Token@github.com/'.insteadOf 'https://github.com/'" -ForegroundColor Gray