# 开发脚本公共函数（dev.ps1 / restart.ps1 共用）
$ErrorActionPreference = 'Stop'

function Get-ProjectRoot {
    $root = Join-Path $PSScriptRoot '..'
    if (-not (Test-Path (Join-Path $root 'app.py'))) {
        throw "未找到 app.py，当前脚本目录: $PSScriptRoot"
    }
    return (Resolve-Path $root).Path
}

function Import-DevLocal {
    param([string]$Root)
    $local = Join-Path $Root 'scripts\dev.local.ps1'
    if (Test-Path $local) {
        . $local
    }
}

function Resolve-PcPython {
    param([string]$Root)
    Import-DevLocal -Root $Root
    $candidates = @(
        $env:PC_PYTHON
        'D:\magic_fox_ai_3_13_3_20250916\resources\backend\python.exe'
        'python'
    ) | Where-Object { $_ -and $_.ToString().Trim() }
    foreach ($exe in $candidates) {
        if ($exe -eq 'python') {
            return $exe
        }
        if (Test-Path $exe) {
            return (Resolve-Path $exe).Path
        }
    }
    throw '未找到 Python。请设置环境变量 PC_PYTHON 或创建 scripts/dev.local.ps1'
}

function Stop-PcServer {
    param([int]$Port = 5050)
    $pids = @()
    try {
        $pids = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch {
        # 部分环境无 Get-NetTCPConnection
    }
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne 0) {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
    Start-Sleep -Milliseconds 400
}

function Start-PcFrontendWatch {
    param([string]$Root)
    if ($env:PC_NO_FRONTEND_WATCH -eq '1') { return $null }
    Write-Host '==> frontend watch (vite build --watch)...'
    return Start-Process -FilePath 'npm' -ArgumentList 'run', 'build:watch' `
        -WorkingDirectory (Join-Path $Root 'frontend') `
        -PassThru -WindowStyle Hidden
}

function Start-PcServer {
    param(
        [string]$Root,
        [string]$Python,
        [switch]$Reload,
        [switch]$NoWorker
    )
    if ($NoWorker) {
        $env:PC_NO_WORKER = '1'
    } else {
        Remove-Item Env:PC_NO_WORKER -ErrorAction SilentlyContinue
    }
    if ($Reload) {
        $env:PC_RELOAD = '1'
    } else {
        Remove-Item Env:PC_RELOAD -ErrorAction SilentlyContinue
    }
    Write-Host "==> Flask http://127.0.0.1:5050  Python=$Python  Reload=$($Reload.IsPresent)"
    return Start-Process -FilePath $Python -ArgumentList 'app.py' `
        -WorkingDirectory $Root -PassThru
}
