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
}
& ".\backend\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\backend\.venv\Scripts\python.exe" -m pip install -e "backend[dev]"

Push-Location frontend
npm.cmd install
Pop-Location

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    $bytes = New-Object byte[] 48
    [Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    $content = Get-Content ".env" -Raw
    $content = $content.Replace("DRIVE_AGENT_APP_SECRET=", "DRIVE_AGENT_APP_SECRET=$secret")
    Set-Content ".env" -Value $content -Encoding utf8
}

Write-Host "Setup hoàn tất." -ForegroundColor Green
Write-Host "Tiếp theo: điền Gemini key, đặt client_secret.json rồi chạy .\scripts\run-dev.ps1"
