param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$Destination,
    [int]$Port = 8000,
    [switch]$ReplaceExisting
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Split-Path $PSScriptRoot -Parent)).Path
if (-not $Destination) { $Destination = Join-Path $repoRoot 'data-restored' }
$backupRoot = (Resolve-Path -LiteralPath $BackupPath).Path
$backupData = Join-Path $backupRoot 'data'
$manifestPath = Join-Path $backupRoot 'manifest.json'
if (-not (Test-Path -LiteralPath $backupData -PathType Container)) { throw 'Backup is missing data/.' }
if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Backup is missing manifest.json.' }

$destinationFull = [System.IO.Path]::GetFullPath($Destination)
$repoPrefix = $repoRoot.TrimEnd('\') + '\'
if (-not $destinationFull.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Restore destination must stay inside the DriveAgent repository.'
}
if ($destinationFull -eq $repoRoot -or $destinationFull -eq (Join-Path $repoRoot 'scripts')) {
    throw 'Unsafe restore destination.'
}

$portInUse = $false
try {
    $listeners = Get-NetTCPConnection -State Listen -ErrorAction Stop
    $portInUse = [bool]($listeners | Where-Object { $_.LocalPort -eq $Port })
} catch {
    $portInUse = [bool](netstat.exe -ano | Select-String (":$Port\s+.*LISTENING"))
}
if ($portInUse) { throw 'Stop DriveAgent before restore. SQLite and Qdrant must be closed.' }

$manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
if ($manifest.schema_version -ne 1 -or $manifest.file_count -ne $manifest.files.Count) {
    throw 'Backup manifest is invalid or incomplete.'
}
foreach ($entry in $manifest.files) {
    $source = Join-Path $backupData ($entry.path.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { throw "Backup file missing: $($entry.path)" }
    if ((Get-Item -LiteralPath $source).Length -ne $entry.size_bytes) { throw "Backup size mismatch: $($entry.path)" }
    if ((Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Backup hash mismatch: $($entry.path)"
    }
}

$quarantine = $null
if (Test-Path -LiteralPath $destinationFull) {
    $existing = Get-ChildItem -LiteralPath $destinationFull -Force -ErrorAction Stop
    if ($existing.Count -gt 0 -and -not $ReplaceExisting) {
        throw 'Destination is not empty. Re-run with -ReplaceExisting to move it aside before restore.'
    }
    if ($existing.Count -gt 0) {
        $quarantine = "$destinationFull.restore-previous-$([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-ffff'))"
        Move-Item -LiteralPath $destinationFull -Destination $quarantine
    }
}
New-Item -ItemType Directory -Path $destinationFull -Force | Out-Null
Copy-Item -Path (Join-Path $backupData '*') -Destination $destinationFull -Recurse -Force

foreach ($entry in $manifest.files) {
    $restored = Join-Path $destinationFull ($entry.path.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $restored -PathType Leaf)) { throw "Restored file missing: $($entry.path)" }
    if ((Get-FileHash -LiteralPath $restored -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.sha256) {
        throw "Restored hash mismatch: $($entry.path)"
    }
}
Write-Host "Restored and SHA256 verified $($manifest.file_count) files: $destinationFull"
if ($quarantine) { Write-Host "Previous destination preserved at: $quarantine" }
Write-Host 'This script restores data only. Restore .env and OAuth secrets separately from encrypted storage.'
