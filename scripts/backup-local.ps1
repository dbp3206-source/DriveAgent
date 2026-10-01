param(
    [int]$Port = 8000,
    [string]$SourceData,
    [string]$BackupRoot
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Split-Path $PSScriptRoot -Parent)).Path
if (-not $SourceData) { $SourceData = Join-Path $repoRoot 'data' }
if (-not $BackupRoot) { $BackupRoot = Join-Path $repoRoot '.local-backups' }
$sourceData = (Resolve-Path -LiteralPath $SourceData).Path
$backupRootFull = [System.IO.Path]::GetFullPath($BackupRoot)
$repoPrefix = $repoRoot.TrimEnd('\') + '\'
if (-not $sourceData.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Backup source must stay inside the DriveAgent repository.'
}
if (-not $backupRootFull.StartsWith($repoPrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Backup destination must stay inside the DriveAgent repository.'
}
$portInUse = $false
try {
    # Get-NetTCPConnection can be blocked by local WMI policy for standard users.
    $listeners = Get-NetTCPConnection -State Listen -ErrorAction Stop
    $portInUse = [bool]($listeners | Where-Object { $_.LocalPort -eq $Port })
} catch {
    # netstat is read-only and available on supported Windows installations.
    $portInUse = [bool](netstat.exe -ano | Select-String (":$Port\s+.*LISTENING"))
}
if ($portInUse) {
    throw 'Stop DriveAgent before backup. SQLite and Qdrant must not change during copy.'
}
if (-not (Test-Path -LiteralPath $sourceData -PathType Container)) { throw 'Missing data/.' }
$target = Join-Path $backupRootFull ([DateTime]::UtcNow.ToString('yyyyMMdd-HHmmss-ffff'))
New-Item -ItemType Directory -Path $target | Out-Null
$targetData = Join-Path $target 'data'
New-Item -ItemType Directory -Path $targetData | Out-Null

# pytest or a failed diagnostic run can leave disposable roots inside data/ with
# ACLs owned by another sandbox identity. They are neither user data nor a valid
# reason to make a production backup impossible. Exclude only these exact root
# names; every other file remains mandatory and is hash-verified below.
$excludedRootNames = @('test_tmp', '.pytest_cache')
$files = @()
foreach ($entry in Get-ChildItem -LiteralPath $sourceData -Force) {
    if ($entry.PSIsContainer) {
        if ($excludedRootNames -contains $entry.Name) { continue }
        $files += Get-ChildItem -LiteralPath $entry.FullName -File -Recurse -Force
    } else {
        $files += $entry
    }
}
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceData.Length).TrimStart('\')
    $copied = Join-Path $targetData $relative
    $copiedParent = Split-Path -Parent $copied
    New-Item -ItemType Directory -Path $copiedParent -Force | Out-Null
    Copy-Item -LiteralPath $file.FullName -Destination $copied
}
$manifestFiles = @()
foreach ($file in $files) {
    $relative = $file.FullName.Substring($sourceData.Length).TrimStart('\')
    $copied = Join-Path $targetData $relative
    $sourceHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $copiedHash = (Get-FileHash -LiteralPath $copied -Algorithm SHA256).Hash
    if ($sourceHash -ne $copiedHash) {
        throw "Backup hash mismatch: $relative. Do not restore this copy."
    }
    $manifestFiles += [ordered]@{
        path = $relative.Replace('\', '/')
        size_bytes = $file.Length
        sha256 = $sourceHash.ToLowerInvariant()
    }
}
$manifest = [ordered]@{
    schema_version = 1
    created_at_utc = [DateTime]::UtcNow.ToString('o')
    file_count = $manifestFiles.Count
    files = $manifestFiles
    excluded_disposable_roots = $excludedRootNames
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $target 'manifest.json') -Encoding utf8
Write-Host "Copied and SHA256 verified $($files.Count) files: $target"
Write-Host 'Wrote manifest.json for pre-restore and post-restore verification.'
Write-Host 'Private data: do not share. Back up .env/secrets separately in encrypted storage.'
Write-Host 'Only default data/ is covered. This script never restores or overwrites the live DB.'
