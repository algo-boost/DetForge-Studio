# DefectLoop Studio — Windows 构建（PyInstaller 目录版 + 可选 Inno Setup）
# Usage: .\packaging\build.ps1 [-CreateInstaller]

param(
    [switch]$CreateInstaller = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "DefectLoop Studio - Windows Build" -ForegroundColor Cyan

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $v = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0 -or $v -match "Python") { $pythonCmd = $cmd; break }
    } catch {}
}
if (-not $pythonCmd) { Write-Host "Python not found" -ForegroundColor Red; exit 1 }

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location frontend
    npm ci 2>$null; if ($LASTEXITCODE -ne 0) { npm install }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Pop-Location
}

& $pythonCmd -m pip install -r requirements.txt -q
& $pythonCmd -m pip install -r requirements-build.txt -q

if (Test-Path "dist") { Remove-Item -Recurse -Force dist }
if (Test-Path "build") { Remove-Item -Recurse -Force build }

& $pythonCmd -m PyInstaller detforge_studio.spec --noconfirm
if ($LASTEXITCODE -ne 0) { exit 1 }

$distDir = Join-Path $ProjectRoot "dist\DefectLoop-Studio"
if (-not (Test-Path $distDir)) {
    Write-Host "Output missing: $distDir" -ForegroundColor Red
    exit 1
}

$ver = (Get-Content version.txt -Raw).Trim()
$zipName = "DefectLoop-Studio-win-$ver.zip"
Compress-Archive -Path $distDir -DestinationPath (Join-Path $ProjectRoot "dist\$zipName") -Force
Write-Host "Created dist\$zipName" -ForegroundColor Green

if ($CreateInstaller -and (Test-Path "packaging\installer\defectloop_studio.iss")) {
    & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer\defectloop_studio.iss
}

Write-Host "Done." -ForegroundColor Green
