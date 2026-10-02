param(
    [Parameter(Mandatory=$true)][int]$TargetProcessId,
    [int]$DurationSeconds = 1800,
    [int]$IntervalSeconds = 10
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskOutput = Join-Path $taskRoot ('design-work/qa/RELEASE-20261002/resources-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $taskOutput | Out-Null
$taskProcess = Get-Process -Id $TargetProcessId
$taskStartIdentity = $taskProcess.StartTime.ToUniversalTime().ToString('o')
$taskClock = [System.Diagnostics.Stopwatch]::StartNew()
$taskSamples = [System.Collections.Generic.List[object]]::new()
$taskResult = 'running'
try {
    while ($taskClock.Elapsed.TotalSeconds -lt $DurationSeconds) {
        $taskProcess = Get-Process -Id $TargetProcessId
        if ($taskProcess.StartTime.ToUniversalTime().ToString('o') -ne $taskStartIdentity) {
            throw 'Process identity changed; refusing to measure a reused PID.'
        }
        $taskSamples.Add([pscustomobject]@{
            elapsedSeconds = [math]::Round($taskClock.Elapsed.TotalSeconds, 2)
            utc = [DateTime]::UtcNow.ToString('o')
            workingSetBytes = $taskProcess.WorkingSet64
            privateBytes = $taskProcess.PrivateMemorySize64
            cpuSeconds = $taskProcess.CPU
            handles = $taskProcess.HandleCount
            threads = $taskProcess.Threads.Count
        })
        $taskSamples | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $taskOutput 'samples.json') -Encoding utf8
        Start-Sleep -Seconds $IntervalSeconds
    }
    $taskResult = 'completed'
} catch {
    $taskResult = 'failed'
    $taskFailure = $_.Exception.Message
} finally {
    $taskReport = [ordered]@{
        pid = $TargetProcessId
        processStartedAt = $taskStartIdentity
        scope = 'Local process only. Workload and cloud memory limits require separate evidence.'
        requestedSeconds = $DurationSeconds
        elapsedSeconds = [math]::Round($taskClock.Elapsed.TotalSeconds, 2)
        status = $taskResult
        failure = $taskFailure
        count = $taskSamples.Count
        samples = $taskSamples
    }
    $taskReport | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskOutput 'report.json') -Encoding utf8
    Write-Output "Resource measurement $taskResult; evidence: $taskOutput"
}
if ($taskResult -ne 'completed') { exit 1 }
