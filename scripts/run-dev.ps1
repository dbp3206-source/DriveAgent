$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendPython = Join-Path $repoRoot "backend\.venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) { throw "Chưa setup. Hãy chạy .\scripts\setup.ps1 trước." }

$backend = Start-Process -FilePath $backendPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000" `
    -WorkingDirectory (Join-Path $repoRoot "backend") `
    -WindowStyle Hidden `
    -PassThru

try {
    Set-Location (Join-Path $repoRoot "frontend")
    npm.cmd run dev
} finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
