$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& ".\backend\.venv\Scripts\python.exe" -m ruff check backend
if ($LASTEXITCODE -ne 0) { throw "Backend lint failed." }
& ".\backend\.venv\Scripts\python.exe" -m pytest backend\tests --cov=app --cov-report=term-missing
if ($LASTEXITCODE -ne 0) { throw "Backend tests failed." }
Push-Location frontend
try {
    npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
} finally {
    Pop-Location
}
Write-Host "Static checks, tests và frontend build đã hoàn tất." -ForegroundColor Green
