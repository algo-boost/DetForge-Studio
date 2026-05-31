"""作业运行日志（写入 exports/job_logs/{job_id}.log，供任务详情页展示）。"""
import os
from datetime import datetime

from studio.paths import PROJECT_ROOT

LOG_DIR = os.path.join(PROJECT_ROOT, 'exports', 'job_logs')


def _path(job_id):
    return os.path.join(LOG_DIR, f'{int(job_id)}.log')


def clear(job_id):
    os.makedirs(LOG_DIR, exist_ok=True)
    p = _path(job_id)
    if os.path.isfile(p):
        os.remove(p)


def append(job_id, message):
    os.makedirs(LOG_DIR, exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f'[{ts}] {message}'
    with open(_path(job_id), 'a', encoding='utf-8') as f:
        f.write(line + '\n')
    return line


def read_tail(job_id, limit=5000):
    p = _path(job_id)
    if not os.path.isfile(p):
        return []
    with open(p, 'r', encoding='utf-8', errors='replace') as f:
        lines = f.read().splitlines()
    if limit and len(lines) > limit:
        return lines[-limit:]
    return lines
