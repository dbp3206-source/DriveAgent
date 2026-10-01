$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$grafanaHome = Join-Path $repoRoot "tools\grafana-10.1.5\grafana-10.1.5"
$grafanaServer = Join-Path $grafanaHome "bin\grafana-server.exe"
$grafanaConfig = Join-Path $repoRoot "ops\native\grafana.ini"
$provisioningPath = Join-Path $repoRoot "ops\native\grafana-provisioning"
$dataPath = Join-Path $repoRoot "data\grafana"

foreach ($requiredPath in @($grafanaServer, $grafanaConfig, $provisioningPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Required local Grafana path is missing: $requiredPath"
    }
}

$portProbe = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 3001)
try {
    $portProbe.Start()
} catch {
    throw "Port 3001 is already in use. Stop the existing Grafana instance explicitly, then rerun this script."
} finally {
    $portProbe.Stop()
}

$env:GF_PATHS_PROVISIONING = $provisioningPath
$env:GF_PATHS_DATA = $dataPath
$env:GF_SERVER_HTTP_ADDR = "127.0.0.1"
$env:GF_SERVER_HTTP_PORT = "3001"

$process = Start-Process `
    -FilePath $grafanaServer `
    -ArgumentList "--config `"$grafanaConfig`" --homepath `"$grafanaHome`"" `
    -WorkingDirectory $repoRoot `
    -WindowStyle Hidden `
    -PassThru

Write-Host "Started local Grafana server (PID $($process.Id)); it is bound to 127.0.0.1:3001."
Write-Host "Provisioning: $provisioningPath"
Write-Host "Data is preserved at: $dataPath"
