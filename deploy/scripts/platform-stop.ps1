# 薄入口 → iisp deploy stop（Windows 原生）
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $Root

function Resolve-Python {
    foreach ($cmd in @('python', 'py', 'python3')) {
        if (Get-Command $cmd -ErrorAction SilentlyContinue) { return $cmd }
    }
    throw '未找到 Python，请安装 Python 3.10+ 并加入 PATH'
}
$py = Resolve-Python
& $py -m cli.main deploy stop @args
exit $LASTEXITCODE
