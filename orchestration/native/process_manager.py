"""原生部署：Kestra / IISP 进程 pid 与健康检查（跨平台 macOS/Linux/Windows）。"""
from __future__ import annotations

import base64
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from orchestration.native.defaults import NativeDeployDefaults, load_defaults
from orchestration.native.kestra_fetch import (
    assets_present,
    ensure_kestra_assets,
    kestra_launch_argv,
    plugins_dir_ready,
)
from orchestration.native.paths import (
    KESTRA_BIN,
    KESTRA_JAR,
    LOG_IISP,
    LOG_KESTRA,
    PID_IISP,
    PID_KESTRA,
    PLUGINS_DIR,
    RUNTIME_ROOT,
    VENDOR_ROOT,
)
from studio.paths import APP_ROOT, CONFIG_FILE

IS_WINDOWS = os.name == 'nt'


class DeployError(Exception):
    pass


def _detached_popen_kwargs() -> dict:
    """让子进程脱离父进程独立后台运行（跨平台）。"""
    if IS_WINDOWS:
        flags = 0
        flags |= getattr(subprocess, 'CREATE_NEW_PROCESS_GROUP', 0)
        flags |= getattr(subprocess, 'DETACHED_PROCESS', 0)
        return {'creationflags': flags}
    return {'start_new_session': True}


@dataclass
class ServiceStatus:
    name: str
    running: bool
    pid: int | None
    url: str
    http_ok: bool


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if IS_WINDOWS:
        # Windows 上 os.kill(pid, 0) 会调用 TerminateProcess（危险），
        # 改用 OpenProcess + GetExitCodeProcess 仅查询存活，不影响目标进程。
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return False
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def read_pid(pid_file: Path) -> int | None:
    if not pid_file.is_file():
        return None
    try:
        return int(pid_file.read_text(encoding='utf-8').strip())
    except ValueError:
        return None


def is_service_running(pid_file: Path) -> bool:
    pid = read_pid(pid_file)
    return pid is not None and _pid_alive(pid)


def _basic_auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f'{user}:{password}'.encode()).decode('ascii')
    return f'Basic {token}'


def wait_http_ok(url: str, *, attempts: int = 30, interval: float = 1.0, auth: tuple[str, str] | None = None) -> bool:
    for _ in range(attempts):
        try:
            req = urllib.request.Request(url)
            if auth:
                req.add_header('Authorization', _basic_auth_header(*auth))
            with urllib.request.urlopen(req, timeout=5):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            time.sleep(interval)
    return False


def _terminate(pid: int, *, force: bool) -> None:
    if IS_WINDOWS:
        # taskkill /T 连同子进程一起结束（Kestra 会派生 JVM 子进程）
        args = ['taskkill', '/PID', str(pid), '/T']
        if force:
            args.append('/F')
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    os.kill(pid, signal.SIGKILL if force else signal.SIGTERM)


def stop_service(name: str, pid_file: Path) -> None:
    pid = read_pid(pid_file)
    if pid is None:
        return
    if not _pid_alive(pid):
        pid_file.unlink(missing_ok=True)
        return
    _terminate(pid, force=False)
    for _ in range(30):
        if not _pid_alive(pid):
            break
        time.sleep(1)
    if _pid_alive(pid):
        _terminate(pid, force=True)
    pid_file.unlink(missing_ok=True)


def ensure_runtime_dirs() -> None:
    RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)


def require_config() -> None:
    if not Path(CONFIG_FILE).is_file():
        raise DeployError(f'缺少 {CONFIG_FILE}（可从设置页配置 DB）')


def require_java() -> str:
    try:
        out = subprocess.check_output(['java', '-version'], stderr=subprocess.STDOUT, text=True)
        return out.splitlines()[0] if out else 'java'
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        hint = 'Temurin/OpenJDK 21 并加入 PATH' if IS_WINDOWS else 'brew install openjdk@21'
        raise DeployError(f'需要 Java 21+（{hint}）') from exc


def require_kestra_assets() -> None:
    if not assets_present():
        raise DeployError(
            f'Kestra 未安装: {KESTRA_JAR} 或 {KESTRA_BIN}（先运行 `iisp deploy fetch`）'
        )


def start_kestra(*, config_yml: Path, defaults: NativeDeployDefaults | None = None) -> int:
    opts = defaults or load_defaults()
    ensure_runtime_dirs()
    if is_service_running(PID_KESTRA):
        pid = read_pid(PID_KESTRA)
        return pid or 0

    require_kestra_assets()
    env = os.environ.copy()
    env['JAVA_OPTS'] = opts.java_opts
    env['ENV_IISP_BASE'] = opts.env_iisp_base

    argv = kestra_launch_argv() + [
        'server', 'standalone',
        '--config', str(config_yml),
        f'--port={opts.kestra_port}',
    ]
    # 仅当 plugins 目录非空才传 --plugins（core 任务已内置于 kestra jar）
    if plugins_dir_ready():
        argv += ['--plugins', str(PLUGINS_DIR)]

    log_fd = open(LOG_KESTRA, 'a', encoding='utf-8')
    try:
        proc = subprocess.Popen(
            argv,
            cwd=str(VENDOR_ROOT),
            env=env,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            **_detached_popen_kwargs(),
        )
    finally:
        log_fd.close()

    PID_KESTRA.write_text(str(proc.pid), encoding='utf-8')
    ok = wait_http_ok(
        opts.kestra_url + '/',
        attempts=60,
        interval=2.0,
        auth=(opts.kestra_user, opts.kestra_password),
    )
    if not ok:
        raise DeployError(f'Kestra 启动超时，见 {LOG_KESTRA}')
    return proc.pid


def start_iisp(*, defaults: NativeDeployDefaults | None = None) -> int:
    opts = defaults or load_defaults()
    ensure_runtime_dirs()
    if is_service_running(PID_IISP):
        pid = read_pid(PID_IISP)
        return pid or 0

    log_fd = open(LOG_IISP, 'a', encoding='utf-8')
    try:
        proc = subprocess.Popen(
            [sys.executable, 'app.py'],
            cwd=str(APP_ROOT),
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            **_detached_popen_kwargs(),
        )
    finally:
        log_fd.close()

    PID_IISP.write_text(str(proc.pid), encoding='utf-8')
    ok = wait_http_ok(f'{opts.iisp_url}/v1/tools', attempts=30, interval=1.0)
    if not ok:
        raise DeployError(f'IISP 启动超时，见 {LOG_IISP}')
    return proc.pid


def collect_status(defaults: NativeDeployDefaults | None = None) -> list[ServiceStatus]:
    opts = defaults or load_defaults()
    rows: list[ServiceStatus] = []
    for name, pid_file, url, auth in (
        ('IISP', PID_IISP, f'{opts.iisp_url}/v1/tools', None),
        ('Kestra', PID_KESTRA, opts.kestra_url + '/', (opts.kestra_user, opts.kestra_password)),
    ):
        pid = read_pid(pid_file)
        running = pid is not None and _pid_alive(pid)
        http_ok = wait_http_ok(url, attempts=1, interval=0, auth=auth) if running else False
        rows.append(ServiceStatus(name=name, running=running, pid=pid, url=url, http_ok=http_ok))
    return rows


def stop_platform() -> None:
    stop_service('Kestra', PID_KESTRA)
    stop_service('IISP', PID_IISP)
