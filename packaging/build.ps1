# DefectLoop Studio — Windows 构建（PyInstaller 目录版 + 捆绑预测/看图工具）
# Usage: .\packaging\build.ps1 [-CreateInstaller] [-SkipTools] [-PythonExe path]

param(
    [switch]$CreateInstaller = $false,
    [switch]$SkipTools = $false,
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $ProjectRoot

Write-Host "DefectLoop Studio - Windows Build" -ForegroundColor Cyan

$localDev = Join-Path $ProjectRoot "scripts\dev.local.ps1"
if (-not $PythonExe -and (Test-Path $localDev)) { . $localDev }
if (-not $PythonExe) { $PythonExe = $env:PC_PYTHON }

$pythonCmd = $null
if ($PythonExe -and (Test-Path $PythonExe)) {
    $pythonCmd = $PythonExe
} else {
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $v = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -or $v -match "Python") { $pythonCmd = $cmd; break }
        } catch {}
    }
}
if (-not $pythonCmd) { Write-Host "Python not found (set PC_PYTHON or -PythonExe)" -ForegroundColor Red; exit 1 }
Write-Host "Using Python: $pythonCmd" -ForegroundColor Green

if (-not (Test-Path "frontend\dist\index.html")) {
    Write-Host "Building frontend..." -ForegroundColor Yellow
    Push-Location frontend
    npm ci 2>$null; if ($LASTEXITCODE -ne 0) { npm install }
    npm run build
    if ($LASTEXITCODE -ne 0) { exit 1 }
    Pop-Location
}

$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $pythonCmd -c "import flask, pandas, pymysql, PIL, sqlalchemy" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing Python dependencies..." -ForegroundColor Yellow
    & $pythonCmd -m pip install --user -r requirements.txt -q 2>$null
}
& $pythonCmd -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) {
    & $pythonCmd -m pip install --user -r requirements-build.txt -q 2>$null
}
$ErrorActionPreference = $prevEap

if (Test-Path "dist") { Remove-Item -Recurse -Force dist }
if (Test-Path "build") { Remove-Item -Recurse -Force build }

& $pythonCmd -m PyInstaller detforge_studio.spec --noconfirm
if ($LASTEXITCODE -ne 0) { exit 1 }

$distDir = Join-Path $ProjectRoot "dist\DefectLoop-Studio"
if (-not (Test-Path $distDir)) {
    Write-Host "Output missing: $distDir" -ForegroundColor Red
    exit 1
}

if (-not $SkipTools) {
    Write-Host "Bundling COCOVisualizer + DetUnify-Studio..." -ForegroundColor Yellow
    & (Join-Path $PSScriptRoot "bundle-tools.ps1") -DistDir $distDir
}

# 首次运行配置模板（预测仍用外部 Python，路径相对 exe 目录）
$cfgExample = Join-Path $PSScriptRoot "config.packaged.json.example"
$cfgDest = Join-Path $distDir "config.json.example"
Copy-Item $cfgExample $cfgDest -Force
if (-not (Test-Path (Join-Path $distDir "config.json"))) {
    Copy-Item $cfgExample (Join-Path $distDir "config.json") -Force
    Write-Host "Created default config.json (edit predict_python_executable before predict jobs)" -ForegroundColor Yellow
}

@(
    "exports", "uploads", "datasets", "uploads\manual_qc"
) | ForEach-Object {
    New-Item -ItemType Directory -Force -Path (Join-Path $distDir $_) | Out-Null
}

$launcher = @"
@echo off
cd /d "%~dp0"
echo DefectLoop Studio -> http://127.0.0.1:5050
echo Predict jobs need predict_python_executable in config.json (Magic-Fox / torch env).
DefectLoop-Studio.exe
pause
"@
Set-Content -Path (Join-Path $distDir "Start-DefectLoop.bat") -Value $launcher -Encoding ASCII

$ver = (Get-Content version.txt -Raw).Trim()
$zipName = "DefectLoop-Studio-win-$ver.zip"
Compress-Archive -Path $distDir -DestinationPath (Join-Path $ProjectRoot "dist\$zipName") -Force
Write-Host "Created dist\$zipName" -ForegroundColor Green

if ($CreateInstaller -and (Test-Path "packaging\installer\defectloop_studio.iss")) {
    & "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" packaging\installer\defectloop_studio.iss
}

Write-Host "Done. Run: $distDir\Start-DefectLoop.bat" -ForegroundColor Green
