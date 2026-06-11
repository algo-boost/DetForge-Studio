"""查询 task（结果页）。"""
from __future__ import annotations

from tools.query.service._app import app_context


def task_get(params: dict) -> dict:
    task_id = str(params.get('task_id') or '').strip()
    if not task_id:
        raise ValueError('task.get 需要 task_id')
    with app_context():
        from flask import current_app
        from server.core import load_query_task_results

        loaded = load_query_task_results(task_id, current_app.config['UPLOAD_FOLDER'])
    if not loaded:
        raise ValueError('任务不存在或缺少 result.csv')
    return {'action': 'task.get', 'task_id': task_id, **loaded}
