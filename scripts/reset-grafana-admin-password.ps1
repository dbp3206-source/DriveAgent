$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$grafanaHome = Join-Path $repoRoot "tools\grafana-10.1.5\grafana-10.1.5"
$grafanaCli = Join-Path $grafanaHome "bin\grafana-cli.exe"
$grafanaConfig = Join-Path $repoRoot "ops\native\grafana.ini"
$grafanaData = Join-Path $repoRoot "data\grafana"

foreach ($requiredPath in @($grafanaCli, $grafanaConfig, $grafanaData)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required local Grafana path is missing: $requiredPath"
    }
}

function Read-PlainPassword {
    param([string]$Prompt)

    $secure = Read-Host -Prompt $Prompt -AsSecureString
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

$first = Read-PlainPassword "New local Grafana admin password"
$second = Read-PlainPassword "Confirm password"

try {
    if ([string]::IsNullOrWhiteSpace($first)) {
        throw "Password cannot be empty."
    }
    if ($first -cne $second) {
        throw "The two password entries do not match."
    }

    $env:GF_PATHS_DATA = $grafanaData
    $first | & $grafanaCli `
        --homepath $grafanaHome `
        --config $grafanaConfig `
        admin reset-admin-password --password-from-stdin --user-id 1

    if ($LASTEXITCODE -ne 0) {
        throw "Grafana CLI password reset failed with exit code $LASTEXITCODE."
    }

    Write-Host "Grafana admin password updated. Sign in with username: admin" -ForegroundColor Green
} finally {
    $first = $null
    $second = $null
}
