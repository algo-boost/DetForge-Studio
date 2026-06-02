# 停止 5050 端口上的 Flask 并重新启动（改完代码后执行）
param(
    [switch]$RebuildFrontend,
    [switch]$NoReload
)

. "$PSScriptRoot\_dev_common.ps1"
$Root = Get-ProjectRoot
$Python = Resolve-PcPython -Root $Root
Set-Location $Root

Write-Host '==> stopping existing server on :5050...'
Stop-PcServer

if ($RebuildFrontend) {
    Write-Host '==> rebuilding frontend...'
    Push-Location (Join-Path $Root 'frontend')
    npm run build
    Pop-Location
}

$appProc = Start-PcServer -Root $Root -Python $Python -Reload:(-not $NoReload)
Write-Host "==> started PID $($appProc.Id)  http://127.0.0.1:5050"
