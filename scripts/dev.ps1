# DefectLoop Studio 本地开发（Windows）：前端 watch + Flask 热重载
param(
    [switch]$NoFrontendWatch,
    [switch]$SkipFrontendBuild
)

. "$PSScriptRoot\_dev_common.ps1"
$Root = Get-ProjectRoot
$Python = Resolve-PcPython -Root $Root
Set-Location $Root

Stop-PcServer

if (-not $SkipFrontendBuild) {
    Write-Host '==> building frontend...'
    Push-Location (Join-Path $Root 'frontend')
    npm run build
    Pop-Location
}

$feProc = $null
if (-not $NoFrontendWatch) {
    $feProc = Start-PcFrontendWatch -Root $Root
}

$appProc = Start-PcServer -Root $Root -Python $Python -Reload

Write-Host ''
Write-Host 'Dev server running. Ctrl+C in this window stops Flask; frontend watch runs in background.'
Write-Host 'Tip: scripts/restart.ps1  — 改完代码后快速重启'
Write-Host ''

try {
    Wait-Process -Id $appProc.Id
} finally {
    if ($feProc -and -not $feProc.HasExited) {
        Stop-Process -Id $feProc.Id -Force -ErrorAction SilentlyContinue
    }
}
