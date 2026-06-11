"""查询执行 — 编排默认 action=execute。"""
from __future__ import annotations

from tools.query.service._app import app_context


def execute(params: dict, *, run_id=None) -> dict:
    from studio.forge import workflow_steps as ws

    with app_context():
        return ws.run_query_step(dict(params), {'run_id': run_id, 'steps': {}})


def preview(params: dict) -> dict:
    """按 strategy_id 预览行数（不落 task）。"""
    from studio.query.strategy_executor import execute_strategy_ref
    from studio.query.strategy_loader import get_all_strategies, get_all_templates
    from tools.query.service._time_window import build_query_context

    strategy_id = params.get('strategy_id')
    if not strategy_id:
        raise ValueError('preview 需要 strategy_id')
    qctx = build_query_context(params)
    ds = params.get('data_source') or 'detail'
    if params.get('predict_job_id'):
        qctx['JOB_ID'] = str(params['predict_job_id'])
    with app_context():
        result = execute_strategy_ref(
            {'strategy_id': str(strategy_id)},
            context=qctx,
            strategies=get_all_strategies(),
            templates=get_all_templates(),
            data_source=ds,
            build_task=False,
        )
    return {
        'action': 'preview',
        'strategy_id': strategy_id,
        'count': int((result or {}).get('count') or 0),
        'row_count': int((result or {}).get('count') or 0),
        'data_source': ds,
    }
