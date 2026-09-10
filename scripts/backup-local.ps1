param([int]$Port = 8000)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
$sourceData = Join-Path $repoRoot 'data'
$listeners = Get-NetTCPConnection -State Listen -ErrorAction Stop
if ($listeners | Where-Object { $_.LocalPort -eq $Port }) {
    throw 'Stop DriveAgent before backup. SQLite and Qdrant must not change during copy.'
}
if (-not (Test-Path -LiteralPath $sourceData -PathType Container)) { throw 'Missing data/.' }
$backupRoot = Join-Path $repoRoot '.local-backups'
$target = Join-Path $backupRoot ([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-ffff'))
New-Item -ItemType Directory -Path $target | Out-Null
Copy-Item -LiteralPath $sourceData -Destination (Join-Path $target 'data') -Recurse
$files = Get-ChildItem -LiteralPath $sourceData -File -Recurse
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceData.Length).TrimStart('\')
    $copied = Join-Path (Join-Path $target 'data') $relative
    if ((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath $copied).Hash) {
        throw "Backup hash mismatch: $relative. Do not restore this copy."
    }
}
Write-Host "Copied and SHA256 verified $($files.Count) files: $target"
Write-Host 'Private data: do not share. Back up .env/secrets separately in encrypted storage.'
Write-Host 'Only default data/ is covered. This script never restores or overwrites the live DB.'
