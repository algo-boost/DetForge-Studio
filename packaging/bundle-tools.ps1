# 将 COCOVisualizer、DetUnify-Studio 复制到 DefectLoop 发行目录 tools/
param(
    [Parameter(Mandatory = $true)]
    [string]$DistDir,

    [string]$ToolsRoot = ""
)

$ErrorActionPreference = "Stop"

if (-not $ToolsRoot) {
    # DetForge-Studio/packaging -> tools/
    $ToolsRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

$DestTools = Join-Path $DistDir "tools"
New-Item -ItemType Directory -Force -Path $DestTools | Out-Null

function Copy-ToolTree {
    param(
        [string]$Name,
        [string]$Source,
        [string[]]$IncludeDirs = @(),
        [string[]]$IncludeFiles = @()
    )
    if (-not (Test-Path $Source)) {
        Write-Host "Skip $Name (missing: $Source)" -ForegroundColor Yellow
        return $false
    }
    $dest = Join-Path $DestTools $Name
    if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
    New-Item -ItemType Directory -Force -Path $dest | Out-Null

    foreach ($d in $IncludeDirs) {
        $srcPath = Join-Path $Source $d
        if (-not (Test-Path $srcPath)) { continue }
        $dstPath = Join-Path $dest $d
        robocopy $srcPath $dstPath /E /NFL /NDL /NJH /NJS /NC /NS /NP /XD node_modules .git __pycache__ .pytest_cache .venv venv build dist frontend | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $Name/$d" }
    }
    foreach ($f in $IncludeFiles) {
        $srcPath = Join-Path $Source $f
        if (Test-Path $srcPath) {
            Copy-Item $srcPath (Join-Path $dest $f) -Force
        }
    }
    Write-Host "Bundled tools/$Name" -ForegroundColor Green
    return
}

$cocoRoot = Join-Path $ToolsRoot "COCOVisualizer"
$detRoot = Join-Path $ToolsRoot "DetUnify-Studio"

# COCOVisualizer 前端 dist
$cocoDist = Join-Path $cocoRoot "static\dist\.vite\manifest.json"
if (-not (Test-Path $cocoDist)) {
    Write-Host "Building COCOVisualizer frontend..." -ForegroundColor Yellow
    Push-Location (Join-Path $cocoRoot "frontend")
    $prevErr = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    npm ci 2>$null; if ($LASTEXITCODE -ne 0) { npm install 2>$null }
    npm run build
    $buildOk = (Test-Path (Join-Path $cocoRoot "static\dist\.vite\manifest.json"))
    $ErrorActionPreference = $prevErr
    Pop-Location
    if (-not $buildOk) { throw "COCOVisualizer frontend build failed" }
}

Copy-ToolTree -Name "COCOVisualizer" -Source $cocoRoot -IncludeDirs @(
    "backend", "static", "templates", "data", "uploads"
) -IncludeFiles @("version.txt")

Copy-ToolTree -Name "DetUnify-Studio" -Source $detRoot -IncludeDirs @(
    "app", "scripts", "src"
) -IncludeFiles @("README.md")

Write-Host "Tools bundle complete -> $DestTools" -ForegroundColor Cyan
