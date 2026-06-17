"""内存 + 文件持久化的后台查询任务（支持并发、切换页面后轮询）。"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from studio.query.query_runner import run_query_request

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JOBS_DIR = os.path.join(BASE_DIR, 'exports', 'query_jobs')
MAX_JOBS = 80

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_executor: ThreadPoolExecutor | None = None
_app = None
_bootstrapped = False


def _ensure_executor():
    global _executor
    if _executor is None:
        workers = max(1, int(os.environ.get('PC_QUERY_WORKERS', '3')))
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='query-job')
    return _executor


def _job_path(job_id: str) -> str:
    os.makedirs(JOBS_DIR, exist_ok=True)
    return os.path.join(JOBS_DIR, f'{job_id}.json')


def _persist(job: dict) -> None:
    try:
        with open(_job_path(job['id']), 'w', encoding='utf-8') as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _update(job_id: str, patch: dict) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        job.update(patch)
        _jobs[job_id] = job
        _persist(job)
        return dict(job)


def init_query_jobs(app) -> None:
    """Flask 启动时注册 app 引用并加载近期任务（进程内仅执行一次）。"""
    global _app, _bootstrapped
    _app = app
    os.makedirs(JOBS_DIR, exist_ok=True)
    if _bootstrapped:
        return
    _bootstrapped = True
    loaded = []
    try:
        for fn in os.listdir(JOBS_DIR):
            if not fn.endswith('.json'):
                continue
            path = os.path.join(JOBS_DIR, fn)
            try:
                with open(path, encoding='utf-8') as f:
                    job = json.load(f)
                if job.get('id'):
                    loaded.append(job)
            except (OSError, json.JSONDecodeError):
                continue
    except OSError:
        pass
    loaded.sort(key=lambda j: j.get('created_at') or 0, reverse=True)
    with _lock:
        for job in loaded[:MAX_JOBS]:
            if job.get('status') in ('pending', 'running'):
                job['status'] = 'failed'
                job['error'] = '服务已重启，任务已中断，请重新执行查询'
                job['finished_at'] = time.time()
                _persist(job)
            _jobs[job['id']] = job


def _run_job(job_id: str, payload: dict) -> None:
    from server.core import (
        build_query_task,
        execute_python_filter,
        get_db_client,
        parse_random_seed,
        sample_size_from_env,
    )
    from server.core import _resolve_query_python

    _update(job_id, {'status': 'running', 'started_at': time.time()})
    try:
        if _app is None:
            raise RuntimeError('query jobs 未初始化')
        with _app.app_context():
            result = run_query_request(
                payload,
                get_db_client=get_db_client,
                execute_python_filter=execute_python_filter,
                build_query_task=build_query_task,
                sample_size_from_env=sample_size_from_env,
                parse_random_seed=parse_random_seed,
                resolve_query_python=_resolve_query_python,
            )
        if not result.get('success'):
            _update(job_id, {
                'status': 'failed',
                'finished_at': time.time(),
                'error': result.get('error') or '查询失败',
            })
            return

        count = int(result.get('count') or 0)
        patch = {
            'status': 'done',
            'finished_at': time.time(),
            'task_id': result.get('task_id') or '',
            'count': count,
            'message': result.get('message') or '',
            'error': '',
        }
        if result.get('execution_time') is not None:
            patch['execution_time'] = result['execution_time']
        if result.get('console_output'):
            patch['console_output'] = result['console_output']
        if result.get('input_rows') is not None:
            patch['input_rows'] = result['input_rows']
            patch['output_rows'] = result.get('output_rows')
        _update(job_id, patch)
    except Exception as e:  # noqa: BLE001
        _update(job_id, {
            'status': 'failed',
            'finished_at': time.time(),
            'error': str(e),
        })


def submit_query_job(payload: dict, *, label: str = '') -> dict:
    """提交后台查询，立即返回 job 元数据。"""
    job_id = str(uuid.uuid4())
    now = time.time()
    body = dict(payload or {})
    if label:
        body['label'] = label
    job = {
        'id': job_id,
        'status': 'pending',
        'label': label or body.get('strategy_id') or '查询',
        'created_at': now,
        'started_at': None,
        'finished_at': None,
        'task_id': '',
        'count': 0,
        'error': '',
        'message': '',
    }
    with _lock:
        _jobs[job_id] = job
        ids = sorted(_jobs.keys(), key=lambda i: _jobs[i].get('created_at') or 0, reverse=True)
        for old_id in ids[MAX_JOBS:]:
            _jobs.pop(old_id, None)
            try:
                os.remove(_job_path(old_id))
            except OSError:
                pass
        _persist(job)

    _ensure_executor().submit(_run_job, job_id, body)
    return dict(job)


def _read_job_file(job_id: str) -> dict | None:
    path = _job_path(job_id)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def get_query_job(job_id: str) -> dict | None:
    """读任务状态；内存与磁盘合并，优先较新的终态/进行中记录。"""
    disk = _read_job_file(job_id)
    with _lock:
        mem = _jobs.get(job_id)
        job = _merge_job_record(mem, disk)
        if job:
            _jobs[job_id] = job
            return dict(job)
        return None


def _job_recency(job: dict | None) -> float:
    if not job:
        return 0.0
    for key in ('finished_at', 'started_at', 'created_at'):
        val = job.get(key)
        if val:
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
    return 0.0


def _merge_job_record(mem: dict | None, disk: dict | None) -> dict | None:
    if mem and disk:
        if _job_recency(mem) >= _job_recency(disk):
            return dict(mem)
        return dict(disk)
    return dict(mem) if mem else (dict(disk) if disk else None)


def list_query_jobs(*, limit: int = 30, active_only: bool = False) -> list[dict]:
    with _lock:
        items = list(_jobs.values())
    items.sort(key=lambda j: j.get('created_at') or 0, reverse=True)
    if active_only:
        items = [j for j in items if j.get('status') in ('pending', 'running')]
    return [dict(j) for j in items[:limit]]
