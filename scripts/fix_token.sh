GITHUB_TOKEN="ghp_...yourtoken..."
curl -i -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
curl -i -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/Precision-Medical-Group/patient-scheduling-solution

curl -i -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/user
# Show repo result + headers: look for X-GitHub-SSO or body text saying SSO is required
curl -i -s -H "Authorization: token $GITHUB_TOKEN" https://api.github.com/repos/Precision-Medical-Group/patient-scheduling-solution | sed -n '1,120p'
