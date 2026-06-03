"""作业运行日志（写入 exports/job_logs/{job_id}.log，供任务详情页展示）。"""
import os
import time
from datetime import datetime

from studio.paths import PROJECT_ROOT

LOG_DIR = os.path.join(PROJECT_ROOT, 'exports', 'job_logs')
_throttle_state = {}


def _path(job_id):
    return os.path.join(LOG_DIR, f'{int(job_id)}.log')


def clear(job_id):
    os.makedirs(LOG_DIR, exist_ok=True)
    p = _path(job_id)
    if os.path.isfile(p):
        os.remove(p)


def append(job_id, message):
    os.makedirs(LOG_DIR, exist_ok=True)
    from studio.timezone_util import format_now
    ts = format_now()
    line = f'[{ts}] {message}'
    with open(_path(job_id), 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return line


def append_throttled(job_id, message, key='progress', min_interval=8.0):
    """限频写入进度类日志，避免每张图打一行撑爆文件。"""
    jid = int(job_id)
    now = time.time()
    state_key = (jid, str(key))
    last = _throttle_state.get(state_key, 0.0)
    if now - last < float(min_interval):
        return None
    _throttle_state[state_key] = now
    return append(jid, message)


def read_tail(job_id, limit=0):
    """读取作业日志。limit=0 表示返回全部行；limit>0 时仅返回末尾 N 行。"""
    p = _path(job_id)
    if not os.path.isfile(p):
        return []
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    if limit and len(lines) > int(limit):
        return lines[-int(limit):]
    return lines
