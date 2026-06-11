"""原生部署：Kestra / IISP 进程 pid 与健康检查。"""
from __future__ import annotations

import base64
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from orchestration.native.defaults import NativeDeployDefaults, load_defaults
from orchestration.native.paths import (
    KESTRA_BIN,
    LOG_IISP,
    LOG_KESTRA,
    PID_IISP,
    PID_KESTRA,
    PLUGINS_DIR,
    RUNTIME_ROOT,
    VENDOR_ROOT,
)
from studio.paths import APP_ROOT, CONFIG_FILE


class DeployError(Exception):
    pass


@dataclass
class ServiceStatus:
    name: str
    running: bool
    pid: int | None
    url: str
    http_ok: bool


def _pid_alive(pid: int) -> bool:
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


def stop_service(name: str, pid_file: Path) -> None:
    pid = read_pid(pid_file)
    if pid is None:
        return
    if not _pid_alive(pid):
        pid_file.unlink(missing_ok=True)
        return
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        if not _pid_alive(pid):
            break
        time.sleep(1)
    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
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
        raise DeployError('需要 Java 21+（brew install openjdk@21）') from exc


def require_kestra_binary() -> Path:
    if not KESTRA_BIN.is_file():
        raise DeployError(f'Kestra 未安装: {KESTRA_BIN}（先运行 fetch_kestra.sh）')
    if not os.access(KESTRA_BIN, os.X_OK):
        KESTRA_BIN.chmod(0o755)
    return KESTRA_BIN


def start_kestra(*, config_yml: Path, defaults: NativeDeployDefaults | None = None) -> int:
    opts = defaults or load_defaults()
    ensure_runtime_dirs()
    if is_service_running(PID_KESTRA):
        pid = read_pid(PID_KESTRA)
        return pid or 0

    bin_path = require_kestra_binary()
    env = os.environ.copy()
    env['JAVA_OPTS'] = opts.java_opts
    env['ENV_IISP_BASE'] = opts.env_iisp_base

    log_fd = open(LOG_KESTRA, 'a', encoding='utf-8')
    try:
        proc = subprocess.Popen(
            [
                str(bin_path),
                'server',
                'standalone',
                '--config',
                str(config_yml),
                '--plugins',
                str(PLUGINS_DIR),
                f'--port={opts.kestra_port}',
            ],
            cwd=str(VENDOR_ROOT),
            env=env,
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
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
            ['python3', 'app.py'],
            cwd=str(APP_ROOT),
            stdout=log_fd,
            stderr=subprocess.STDOUT,
            start_new_session=True,
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
