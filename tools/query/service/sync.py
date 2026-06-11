"""同步查询 — 对应 POST /api/query（SQL + Python 完整管线）。"""
from __future__ import annotations

from tools.query.service._app import app_context


def run_sync(params: dict) -> dict:
    with app_context():
        from server.core import (
            build_query_task,
            execute_python_filter,
            get_db_client,
            parse_random_seed,
            sample_size_from_env,
        )
        from server.core import _resolve_query_python
        from studio.query.query_runner import run_query_request

        result = run_query_request(
            dict(params or {}),
            get_db_client=get_db_client,
            execute_python_filter=execute_python_filter,
            build_query_task=build_query_task,
            sample_size_from_env=sample_size_from_env,
            parse_random_seed=parse_random_seed,
            resolve_query_python=_resolve_query_python,
        )
    out = {'action': 'run', **result}
    if result.get('success') and result.get('task_id'):
        out.setdefault('row_count', result.get('count', 0))
    return out
