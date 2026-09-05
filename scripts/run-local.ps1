$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $backendPython)) {
    throw "Run scripts/setup.ps1 first."
}
Push-Location $repoRoot
try {
    & $backendPython scripts/local_config.py
    if ($LASTEXITCODE -ne 0) { throw "Complete docs/START_LOCAL.md before starting." }

    # Build once, then serve UI and API on the same origin. No Vite dev server needed.
    npm.cmd run build --prefix frontend
    if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }

    # OAuthlib normally requires HTTPS. This exception is limited to this loopback-only
    # process; never bind this runner to 0.0.0.0 or expose it through a public tunnel.
    $previousTransport = $env:OAUTHLIB_INSECURE_TRANSPORT
    $env:OAUTHLIB_INSECURE_TRANSPORT = "1"
    try {
        Write-Host "Open http://localhost:8000 . Stop with Ctrl+C."
        # Access log mặc định ghi toàn bộ query, gồm code OAuth tại callback.
        & $backendPython -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
        if ($LASTEXITCODE -ne 0) { throw "Local server stopped with an error." }
    } finally {
        $env:OAUTHLIB_INSECURE_TRANSPORT = $previousTransport
    }
} finally {
    Pop-Location
}
