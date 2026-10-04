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
            $runtimeInfo = & $exe @args -c "import sys, sysconfig; print(sysconfig.get_platform() + '|' + '.'.join(map(str, sys.version_info[:2])))" 2>$null
            $runtimeParts = "$runtimeInfo" -split '\|'
            if ($LASTEXITCODE -eq 0 -and $runtimeParts.Count -eq 2 -and $runtimeParts[0] -like "win-*" -and $runtimeParts[1] -in @("3.11", "3.12")) {
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
& ".\backend\.venv\Scripts\python.exe" -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 11), (3, 12)) else 1)"
if ($LASTEXITCODE -ne 0) {
    throw "Môi trường backend/.venv không dùng Python 3.11/3.12. Giữ nguyên dữ liệu; chuyển riêng thư mục .venv cũ sang tên dự phòng rồi chạy lại setup."
}
& ".\backend\.venv\Scripts\python.exe" -m pip install "uv==0.12.19"
if ($LASTEXITCODE -ne 0) { throw "Locked installer installation failed." }
# Use the same versioned lock as CI; do not resolve fresh dependency versions.
& ".\backend\.venv\Scripts\python.exe" -m uv sync --project backend --frozen --extra dev --python ".\backend\.venv\Scripts\python.exe"
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
