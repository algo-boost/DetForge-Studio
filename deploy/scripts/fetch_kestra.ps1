# 获取 Kestra 运行资产（Windows 原生）→ deploy/vendor/kestra.jar
# 等价于 fetch_kestra.sh，但跨平台逻辑统一委托给 Python（orchestration.native.kestra_fetch）。
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
& $py -m cli.main deploy fetch @args
exit $LASTEXITCODE
