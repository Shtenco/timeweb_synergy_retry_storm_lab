# For Windows with an authenticated Git Credential Manager and a new, empty GitHub repo.
param([string]$Repo = "Shtenco/timeweb_synergy_retry_storm_lab")
$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
if (!(Test-Path .git)) { throw "Local .git missing: restore repository bundle first" }
$origin = git remote get-url origin 2>$null
if (!$origin) { git remote add origin "https://github.com/$Repo.git" }
git push -u origin main
Write-Host "Published: https://github.com/$Repo"
