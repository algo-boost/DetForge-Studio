"""原生部署：IISP 进程 pid 与健康检查（跨平台 macOS/Linux/Windows）。"""
from __future__ import annotations

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
from orchestration.native.paths import LOG_IISP, PID_IISP, RUNTIME_ROOT
from studio.paths import APP_ROOT, CONFIG_FILE

IS_WINDOWS = os.name == 'nt'


class DeployError(Exception):
    pass


def _detached_popen_kwargs() -> dict:
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


def wait_http_ok(url: str, *, attempts: int = 30, interval: float = 1.0) -> bool:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(url, timeout=5):
                return True
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError):
            time.sleep(interval)
    return False


def _terminate(pid: int, *, force: bool) -> None:
    if IS_WINDOWS:
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


def start_iisp(*, defaults: NativeDeployDefaults | None = None) -> int:
    opts = defaults or load_defaults()
    ensure_runtime_dirs()
    if is_service_running(PID_IISP):
        pid = read_pid(PID_IISP)
        return pid or 0

    log_fd = open(LOG_IISP, 'a', encoding='utf-8')
    env = os.environ.copy()
    env['IISP_PORT'] = str(opts.iisp_port)
    try:
        proc = subprocess.Popen(
            [sys.executable, 'app.py'],
            cwd=str(APP_ROOT),
            env=env,
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
    pid = read_pid(PID_IISP)
    running = pid is not None and _pid_alive(pid)
    url = f'{opts.iisp_url}/v1/tools'
    http_ok = wait_http_ok(url, attempts=1, interval=0) if running else False
    rows.append(ServiceStatus(name='IISP', running=running, pid=pid, url=url, http_ok=http_ok))
    return rows


def stop_platform() -> None:
    stop_service('IISP', PID_IISP)
