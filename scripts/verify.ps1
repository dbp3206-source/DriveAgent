$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& ".\backend\.venv\Scripts\python.exe" -m ruff check backend
& ".\backend\.venv\Scripts\python.exe" -m pytest backend\tests --cov=app --cov-report=term-missing
Push-Location frontend
npm.cmd run lint
npm.cmd run build
Pop-Location
Write-Host "Static checks, tests và frontend build đã hoàn tất." -ForegroundColor Green
