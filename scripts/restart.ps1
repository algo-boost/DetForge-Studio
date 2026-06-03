<#
.SYNOPSIS
  停止 5050 端口上的 DefectLoop Studio 并重新启动 Flask。

.DESCRIPTION
  默认只重启后端（不编译前端）。改前端后请带 -RebuildFrontend 或 -Full，或双击 restart-full.bat。

.EXAMPLE
  .\scripts\restart.ps1
  仅重启后端（最快）

.EXAMPLE
  .\scripts\restart.ps1 -RebuildFrontend
  .\scripts\restart.ps1 -Full
  先 npm run build 再重启（前端有改动时用）

.EXAMPLE
  .\scripts\restart.ps1 -Reload
  开启 Flask 热重载（长期开发建议用 dev.ps1）
#>
param(
    [switch]$RebuildFrontend,
    [switch]$Full,       # 等同 -RebuildFrontend：后端 + 前端完整重启
    [switch]$Reload      # 默认关，避免后台任务被热重载打断
)

if ($Full) { $RebuildFrontend = $true }

. "$PSScriptRoot\_dev_common.ps1"
$Root = Get-ProjectRoot
$Python = Resolve-PcPython -Root $Root
Set-Location $Root

Write-Host '==> stopping existing server on :5050...'
Stop-PcServer

if ($RebuildFrontend) {
    Write-Host '==> rebuilding frontend (npm run build)...'
    Push-Location (Join-Path $Root 'frontend')
    if (-not (Test-Path 'node_modules')) {
        Write-Host '==> npm install (first time)...'
        npm install
    }
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        throw "前端构建失败，退出码 $LASTEXITCODE"
    }
    Pop-Location
    Write-Host '==> frontend build OK'
} else {
    Write-Host '==> skip frontend build (use -RebuildFrontend or -Full if UI changed)'
}

$appProc = Start-PcServer -Root $Root -Python $Python -Reload:$Reload
Write-Host "==> started PID $($appProc.Id)  http://127.0.0.1:5050"
