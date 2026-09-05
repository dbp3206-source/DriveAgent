$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

function Find-Python {
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $candidates += ,@("py", "-3.12")
        $candidates += ,@("py", "-3.11")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $candidates += ,@("python")
    }
    # Codex Desktop có thể kèm Python Windows riêng dù lệnh `python` của máy trỏ
    # nhầm sang MSYS2. Chỉ dùng fallback này khi file thực sự tồn tại.
    $codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
    if (Test-Path -LiteralPath $codexPython) {
        $candidates += ,@($codexPython)
    }
    foreach ($candidate in $candidates) {
        $exe = $candidate[0]
        $args = @($candidate | Select-Object -Skip 1)
        try {
            $platform = & $exe @args -c "import sysconfig; print(sysconfig.get_platform())"
            if ($LASTEXITCODE -eq 0 -and $platform -like "win-*") {
                return @{ Exe = $exe; Args = $args }
            }
        } catch {}
    }
    throw "Cần Python 3.11/3.12 bản Windows từ https://python.org. Bản MSYS2 không tương thích wheel native."
}

$python = Find-Python
if (-not (Test-Path ".\backend\.venv\Scripts\python.exe")) {
    & $python.Exe @($python.Args) -m venv ".\backend\.venv"
    if ($LASTEXITCODE -ne 0) { throw "Python venv creation failed." }
}
& ".\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
& ".\backend\.venv\Scripts\python.exe" -m pip install -e "backend[dev]"
if ($LASTEXITCODE -ne 0) { throw "Backend dependency installation failed." }

Push-Location frontend
try {
    npm.cmd ci
    if ($LASTEXITCODE -ne 0) { throw "Frontend dependency installation failed." }
} finally {
    Pop-Location
}

& ".\backend\.venv\Scripts\python.exe" scripts/local_config.py --prepare
if ($LASTEXITCODE -ne 0) { throw "Local configuration preparation failed." }

Write-Host "Setup hoàn tất." -ForegroundColor Green
Write-Host "Next: follow docs/START_LOCAL.md, then run scripts/run-local.ps1"
