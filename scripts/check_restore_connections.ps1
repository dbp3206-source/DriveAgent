$ErrorActionPreference = 'Stop'
# Read-only prerequisite. Passwords are entered directly at psql's hidden prompt.
# No credentials, application rows, or connection URLs containing passwords are saved.
$restorePsql = 'C:\Program Files\PostgreSQL\17\bin\psql.exe'
if (-not (Test-Path -LiteralPath $restorePsql)) { throw 'Chưa tìm thấy PostgreSQL 17.' }
if ($env:PGPASSWORD -or $env:PGSERVICE) {
    throw 'Dùng cửa sổ PowerShell mới không có PGPASSWORD hoặc PGSERVICE; không nhập khóa vào lệnh.'
}
$restoreChecks = @(
    @{ Label = 'NGUỒN đang chạy'; Ref = 'ltvzdrvjmljvrnhwxade' },
    @{ Label = 'ĐÍCH thử riêng'; Ref = 'scsxkanbmtexylgbrsla' }
)
$restoreQuery = "BEGIN READ ONLY; SELECT current_user, current_setting('server_version'), (SELECT count(*) FROM pg_tables WHERE schemaname='veridra_private') AS private_tables, (SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()) AS encrypted_connection; COMMIT;"
foreach ($restoreCheck in $restoreChecks) {
    Write-Host "Nhập mật khẩu database của $($restoreCheck.Label), project $($restoreCheck.Ref)."
    $restoreConnection = "host=aws-0-ap-south-1.pooler.supabase.com port=5432 dbname=postgres user=postgres.$($restoreCheck.Ref) sslmode=require connect_timeout=15 application_name=veridra_restore_readonly_check"
    & $restorePsql -X --password --dbname=$restoreConnection --set=ON_ERROR_STOP=1 --command=$restoreQuery
    if ($LASTEXITCODE -ne 0) { throw "Chưa kết nối được $($restoreCheck.Label); dừng, không ghi dữ liệu." }
}
Write-Host 'Hai phép kiểm kết nối hoàn tất. Chưa sao lưu hoặc khôi phục dữ liệu.'
