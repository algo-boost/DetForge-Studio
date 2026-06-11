"""跨平台获取 Kestra 运行资产，并生成启动命令。

- macOS/Linux：优先复用 deploy/scripts/fetch_kestra.sh（Docker 提取，插件最全）；
  无 bash/Docker 时回退到 API 下载。
- Windows：下载 Kestra 可执行 uber-jar 到 deploy/vendor/kestra.jar，
  通过 `java -jar kestra.jar ...` 运行；core 插件已内置于该 jar。

启动命令统一由 kestra_launch_argv() 生成：
- 存在 kestra.jar     → ['java', '-jar', <jar>]
- 存在可执行 kestra   → [<bin>]（posix）
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from orchestration.native.defaults import NativeDeployDefaults, load_defaults
from orchestration.native.paths import (
    DEPLOY_ROOT,
    KESTRA_BIN,
    KESTRA_JAR,
    PLUGINS_DIR,
    VENDOR_ROOT,
)

IS_WINDOWS = os.name == 'nt'


class KestraFetchError(Exception):
    pass


def assets_present() -> bool:
    """已具备可启动的 Kestra 资产（jar 或原生可执行）。"""
    if KESTRA_JAR.is_file():
        return True
    return KESTRA_BIN.is_file() and (IS_WINDOWS or os.access(KESTRA_BIN, os.X_OK))


def kestra_launch_argv() -> list[str]:
    """返回启动 Kestra 的基础命令（不含 server/standalone 等子命令）。"""
    if KESTRA_JAR.is_file():
        return ['java', '-jar', str(KESTRA_JAR)]
    if KESTRA_BIN.is_file():
        if IS_WINDOWS:
            # Windows 上原生 ELF/Mach-O 不可执行，但它是合法 uber-jar
            return ['java', '-jar', str(KESTRA_BIN)]
        return [str(KESTRA_BIN)]
    raise KestraFetchError(
        f'Kestra 未安装：{KESTRA_JAR} 或 {KESTRA_BIN} 均不存在（先运行 deploy fetch）'
    )


def plugins_dir_ready() -> bool:
    return PLUGINS_DIR.is_dir() and any(PLUGINS_DIR.iterdir())


def _download_jar(version: str) -> None:
    VENDOR_ROOT.mkdir(parents=True, exist_ok=True)
    url = f'https://api.kestra.io/v1/releases/{version}/download/kestra'
    tmp = KESTRA_JAR.with_suffix('.jar.download')
    print(f'    下载 Kestra {version} → {KESTRA_JAR}')
    with urllib.request.urlopen(url, timeout=600) as resp, open(tmp, 'wb') as f:
        shutil.copyfileobj(resp, f)
    tmp.replace(KESTRA_JAR)
    if not IS_WINDOWS:
        try:
            KESTRA_JAR.chmod(0o755)
        except OSError:
            pass


def _install_core_plugins() -> None:
    """安装 core 插件到 PLUGINS_DIR（best-effort；core 通常已内置于 jar）。"""
    PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    if plugins_dir_ready():
        return
    argv = kestra_launch_argv() + [
        'plugins', 'install', 'io.kestra.plugin.core', '--plugins', str(PLUGINS_DIR),
    ]
    try:
        subprocess.run(argv, check=True)
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f'    警告：core 插件安装失败（{exc}）；core 任务通常已内置于 kestra jar，可忽略。')


def ensure_kestra_assets(defaults: NativeDeployDefaults | None = None) -> None:
    """确保 Kestra 资产就绪。已存在则跳过。"""
    if assets_present():
        return
    opts = defaults or load_defaults()

    # posix：优先复用经过验证的 bash 脚本（Docker 提取插件最全）
    fetch_sh = DEPLOY_ROOT / 'scripts' / 'fetch_kestra.sh'
    if not IS_WINDOWS and shutil.which('bash') and fetch_sh.is_file():
        print('==> 获取 Kestra（fetch_kestra.sh）')
        try:
            subprocess.check_call(['bash', str(fetch_sh)])
            if assets_present():
                return
        except subprocess.CalledProcessError:
            print('    fetch_kestra.sh 失败，回退到 API 下载…')

    # 跨平台：API 下载 uber-jar
    print('==> 获取 Kestra（API 下载 jar）')
    _require_java()
    _download_jar(opts.kestra_version)
    _install_core_plugins()
    if not assets_present():
        raise KestraFetchError('Kestra 资产获取失败')


def _require_java() -> None:
    if shutil.which('java') is None:
        raise KestraFetchError('需要 Java 21+（Windows 可安装 Temurin/OpenJDK 21 并加入 PATH）')


def main() -> int:
    ensure_kestra_assets()
    print(f'OK Kestra 就绪：{" ".join(kestra_launch_argv())}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
