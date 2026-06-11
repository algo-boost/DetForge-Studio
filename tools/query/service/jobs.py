"""查询 job（异步提交 / 状态 / 历史列表）。"""
from __future__ import annotations

from tools.query.service._app import app_context


def job_submit(params: dict) -> dict:
    payload = dict(params.get('query') or params)
    label = str(payload.pop('label', None) or payload.pop('strategy_name', None) or '').strip()
    if not str(payload.get('sql', '')).strip() and not payload.get('strategy_id'):
        raise ValueError('job.submit 需要 sql 或 strategy_id')
    with app_context():
        from studio.query import query_jobs
        job = query_jobs.submit_query_job(payload, label=label)
    return {'action': 'job.submit', 'query_job_id': job['id'], 'job': job}


def job_get(params: dict) -> dict:
    job_id = params.get('job_id') or params.get('query_job_id')
    if not job_id:
        raise ValueError('job.get 需要 job_id')
    with app_context():
        from studio.query import query_jobs
        job = query_jobs.get_query_job(job_id)
    if not job:
        raise ValueError('任务不存在')
    return {'action': 'job.get', 'job': job}


def job_list(params: dict) -> dict:
    limit = min(100, int(params.get('limit') or 30))
    active_only = str(params.get('active_only') or '').lower() in ('1', 'true', 'yes')
    with app_context():
        from studio.query import query_jobs
        jobs = query_jobs.list_query_jobs(limit=limit, active_only=active_only)
    return {'action': 'job.list', 'count': len(jobs), 'jobs': jobs}


def history_list(params: dict) -> dict:
    """查询历史 — 与 job.list 同源。"""
    out = job_list(params)
    out['action'] = 'history.list'
    return out
