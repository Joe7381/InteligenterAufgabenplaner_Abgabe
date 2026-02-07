# upload_to_github.ps1
#
# Usage: Open PowerShell in project folder
# Interactive:
# PS> .\upload_to_github.ps1
# With parameters:
# PS> .\upload_to_github.ps1 -RepoName "MyRepo" -Visibility "public"
#
# This script:
# - Checks Git and optionally GitHub CLI (gh) and installs via winget if available
# - Initializes local Git repo, adds files and commits
# - Creates repo on GitHub via gh or GitHub API with PAT
# - Adds remote and pushes
#
# Security: Never share your Personal Access Token (PAT) in public. This script asks for it locally if needed.

param(
    [string]$RepoName = $(Read-Host "Repo name (will be created under your GitHub account)"),
    [ValidateSet('public','private')][string]$Visibility = 'public',
    [switch]$ForceInstallViaWinget
)

function Ensure-Command {
    param(
        [string]$Cmd,
        [string]$WingetId
    )
    try {
        & $Cmd --version > $null 2>&1
        return $true
    } catch {
        Write-Host "$Cmd is not installed or not in PATH." -ForegroundColor Yellow
        if ($ForceInstallViaWinget -or (Get-Command winget -ErrorAction SilentlyContinue)) {
            if (Get-Command winget -ErrorAction SilentlyContinue) {
                Write-Host "Trying to install $Cmd via winget..." -ForegroundColor Cyan
                winget install --id $WingetId -e --accept-package-agreements --accept-source-agreements
                Start-Sleep -Seconds 2
                try { & $Cmd --version > $null 2>&1; return $true } catch { Write-Host "Installation via winget failed or PATH not updated." -ForegroundColor Red; return $false }
            } else {
                Write-Host "winget not found. Please install $Cmd manually (https://git-scm.com/ or https://cli.github.com/)." -ForegroundColor Red
                return $false
            }
        } else {
            Write-Host "winget not found. Set -ForceInstallViaWinget or install $Cmd manually." -ForegroundColor Red
            return $false
        }
    }
}

# 1) Ensure Git is available
if (-not (Ensure-Command -Cmd 'git' -WingetId 'Git.Git')) {
    Write-Host "Git is required. Please install Git and restart this script." -ForegroundColor Red
    exit 1
}

# 2) Initialize Git repo if needed
if (-not (Test-Path -Path .git)) {
    Write-Host "Initializing Git repository..."
    git init
} else {
    Write-Host "Git repository already exists." -ForegroundColor Green
}

# 3) Add files and commit
Write-Host "Adding files and creating commit (if there are changes)..."
git add .
$changes = git status --porcelain
if ($changes) {
    git commit -m "Initial commit"
} else {
    Write-Host "No changes to commit." -ForegroundColor Yellow
}

# 4) Check if gh is available
$ghAvailable = $false
if (Ensure-Command -Cmd 'gh' -WingetId 'GitHub.cli') {
    $ghAvailable = $true
}

if ($ghAvailable) {
    Write-Host "GitHub CLI (gh) available. Checking authentication..."
    try {
        gh auth status > $null 2>&1
        Write-Host "Already authenticated with GitHub." -ForegroundColor Green
    } catch {
        Write-Host "Not logged in to gh. Starting interactive browser login..." -ForegroundColor Cyan
        gh auth login --web
    }

    Write-Host "Creating repo via gh and pushing..."
    gh repo create $RepoName --$Visibility --source=. --remote=origin --push --confirm
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Repo successfully created and pushed." -ForegroundColor Green
    } else {
        Write-Host "Error creating/pushing with gh. Trying manual method." -ForegroundColor Red
    }
    exit 0
}

# 5) If gh not available: Create repo via GitHub API (needs PAT)
Write-Host "gh not available. Creating repo via GitHub API (Personal Access Token needed)." -ForegroundColor Yellow
$tokenSecure = Read-Host -AsSecureString "Enter your GitHub Personal Access Token (scope: repo) - input is hidden"
# Convert SecureString to plaintext (local only, not in logs)
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($tokenSecure)
$token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
[Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)

$body = @{ name = $RepoName; private = ($Visibility -eq 'private') } | ConvertTo-Json
$headers = @{ Authorization = "token $token"; "User-Agent" = $env:USERNAME }

try {
    $response = Invoke-RestMethod -Method Post -Uri 'https://api.github.com/user/repos' -Headers $headers -Body $body -ContentType 'application/json'
    Write-Host "Repo created on GitHub: $($response.html_url)" -ForegroundColor Green
    $remoteUrl = $response.clone_url
} catch {
    Write-Host "Error creating repo via API: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# 6) Add remote and push
try {
    git remote add origin $remoteUrl
} catch {
    Write-Host "Remote origin already exists or could not be added." -ForegroundColor Yellow
}

git branch -M main
Write-Host "Pushing to origin main..."
git push -u origin main

Write-Host "Done. Check your GitHub repo." -ForegroundColor Green
