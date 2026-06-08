"""跟踪并终止 DetForge 拉起的子进程（预测 worker、抓取脚本等）。"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from datetime import datetime, timezone

from studio.paths import APP_ROOT

logger = logging.getLogger('detforge.process_registry')

REGISTRY_FILE = os.path.join(APP_ROOT, 'exports', '.child_processes.json')
_lock = threading.Lock()
_registered: dict[int, str] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_file() -> dict:
    try:
        with open(REGISTRY_FILE, encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_file(data: dict) -> None:
    os.makedirs(os.path.dirname(REGISTRY_FILE), exist_ok=True)
    with open(REGISTRY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _persist_locked() -> None:
    data = _load_file()
    data['updated_at'] = _now_iso()
    data['pids'] = {str(pid): label for pid, label in _registered.items()}
    _save_file(data)


def register_child(pid: int, label: str = 'child') -> None:
    if not pid:
        return
    with _lock:
        _registered[int(pid)] = str(label or 'child')
        _persist_locked()


def unregister_child(pid: int) -> None:
    if not pid:
        return
    with _lock:
        _registered.pop(int(pid), None)
        _persist_locked()


def _pid_alive(pid: int) -> bool:
    if not pid:
        return False
    if sys.platform == 'win32':
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, int(pid))
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def kill_process_tree(pid: int) -> bool:
    """终止进程及其子进程；返回是否发起了 kill。"""
    pid = int(pid)
    if not _pid_alive(pid):
        return False
    try:
        if sys.platform == 'win32':
            proc = subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(pid)],
                capture_output=True,
                text=True,
            )
            return proc.returncode == 0
        import signal
        os.killpg(os.getpgid(pid), signal.SIGKILL)
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning('kill pid=%s failed: %s', pid, e)
        try:
            os.kill(pid, 9 if sys.platform != 'win32' else 1)
            return True
        except OSError:
            return False


def kill_all_registered() -> int:
    """终止当前会话登记的全部子进程；返回 kill 尝试次数。"""
    with _lock:
        pids = list(_registered.keys())
    killed = 0
    for pid in pids:
        if kill_process_tree(pid):
            killed += 1
        unregister_child(pid)

    stale = _load_file().get('pids') or {}
    for pid_s in list(stale.keys()):
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            continue
        if kill_process_tree(pid):
            killed += 1
    with _lock:
        _registered.clear()
        _save_file({'updated_at': _now_iso(), 'pids': {}})
    return killed


def cleanup_orphans_on_startup() -> int:
    """启动时清理上次会话遗留的子进程登记。"""
    data = _load_file()
    pids = data.get('pids') or {}
    killed = 0
    for pid_s in list(pids.keys()):
        try:
            pid = int(pid_s)
        except (TypeError, ValueError):
            continue
        if kill_process_tree(pid):
            killed += 1
            logger.info('已终止遗留子进程 pid=%s (%s)', pid, pids.get(pid_s))
    with _lock:
        _registered.clear()
        _save_file({'updated_at': _now_iso(), 'pids': {}})
    return killed
