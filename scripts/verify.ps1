$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

& ".\backend\.venv\Scripts\python.exe" -m ruff check backend
if ($LASTEXITCODE -ne 0) { throw "Backend lint failed." }
Push-Location backend
try {
    & ".\.venv\Scripts\python.exe" -m ruff check ..\scripts
    if ($LASTEXITCODE -ne 0) { throw "Script lint failed." }
} finally {
    Pop-Location
}
& ".\backend\.venv\Scripts\python.exe" -m pip check
if ($LASTEXITCODE -ne 0) { throw "Backend dependency check failed." }
# Keep the evaluation contract in the same local verification path as code and
# frontend checks.  This validates the Gate 2 manifest structure only; strict
# source hashing and live model/human review remain explicit QA gates because
# they depend on user-provided files and provider access.
& ".\backend\.venv\Scripts\python.exe" scripts\validate_gate2.py
if ($LASTEXITCODE -ne 0) { throw "Gate 2 evaluation manifest validation failed." }
$verifyPytestTemp = Join-Path $repoRoot "design-work\qa\validation\verify-pytest-temp"
$resolvedVerifyPytestTemp = [System.IO.Path]::GetFullPath($verifyPytestTemp)
$resolvedRepoRoot = [System.IO.Path]::GetFullPath($repoRoot)
if (-not $resolvedVerifyPytestTemp.StartsWith($resolvedRepoRoot + [System.IO.Path]::DirectorySeparatorChar)) {
    throw "Refusing to use a pytest temporary directory outside the repository."
}
try {
    & ".\backend\.venv\Scripts\python.exe" -m pytest backend\tests --basetemp $resolvedVerifyPytestTemp --cov=app --cov-report=term-missing --cov-fail-under=85
    $backendTestExitCode = $LASTEXITCODE
} finally {
    if (Test-Path -LiteralPath $resolvedVerifyPytestTemp) {
        Remove-Item -LiteralPath $resolvedVerifyPytestTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
if ($backendTestExitCode -ne 0) { throw "Backend tests or coverage gate failed." }
Push-Location frontend
try {
    npm.cmd test
    if ($LASTEXITCODE -ne 0) { throw "Frontend tests failed." }
    npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
    # Never rebuild frontend/dist while a local server may be serving its
    # hashed chunks: deleting those chunks breaks every already-open browser
    # tab. Build into an isolated directory, validate it, then remove only that
    # known workspace path.
    $verifyDist = Join-Path (Get-Location) ".verify-dist"
    $frontendRoot = [System.IO.Path]::GetFullPath((Get-Location).Path)
    $resolvedVerifyDist = [System.IO.Path]::GetFullPath($verifyDist)
    if (-not $resolvedVerifyDist.StartsWith($frontendRoot + [System.IO.Path]::DirectorySeparatorChar)) {
        throw "Refusing to use a verification directory outside frontend/."
    }
    try {
        npm.cmd run build -- --outDir .verify-dist
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
        if (-not (Test-Path -LiteralPath (Join-Path $verifyDist "index.html"))) {
            throw "Frontend verification build did not produce index.html."
        }
    } finally {
        if (Test-Path -LiteralPath $resolvedVerifyDist) {
            Remove-Item -LiteralPath $resolvedVerifyDist -Recurse -Force
        }
    }
} finally {
    Pop-Location
}
Write-Host "Dependencies, lint, tests, coverage và frontend build đã hoàn tất." -ForegroundColor Green
