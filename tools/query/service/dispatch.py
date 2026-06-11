"""查询域统一 dispatch — 单工具多 action。"""
from __future__ import annotations

# 编排/Kestra 无 action 且有 strategy_id → execute
# 旧 query-strategy 工具 action=list|get|... → strategy.*

_LEGACY_STRATEGY_ACTIONS = frozenset({
    'list', 'get', 'variables', 'validate', 'save', 'delete', 'execute', 'compile_pipeline',
})

KNOWN_ACTIONS = frozenset({
    'execute',
    'run',
    'preview',
    'task.get',
    'job.submit',
    'job.get',
    'job.list',
    'history.list',
    'strategy.list',
    'strategy.get',
    'strategy.variables',
    'strategy.validate',
    'strategy.save',
    'strategy.delete',
    'strategy.execute',
    'strategy.compile_pipeline',
})


def resolve_action(params: dict | None) -> str:
    params = dict(params or {})
    raw = params.get('action')
    if raw is None or str(raw).strip() == '':
        if params.get('strategy_id') or params.get('strategy'):
            return 'execute'
        return 'strategy.list'
    action = str(raw).strip().lower()
    if action in _LEGACY_STRATEGY_ACTIONS:
        return f'strategy.{action}'
    return action


def dispatch(params: dict | None, *, run_id=None) -> dict:
    """路由到子模块；返回 outputs dict。"""
    params = dict(params or {})
    action = resolve_action(params)

    if action == 'execute':
        from tools.query.service.execute import execute
        exec_params = {k: v for k, v in params.items() if k != 'action'}
        return execute(exec_params, run_id=run_id)

    if action == 'run':
        from tools.query.service.sync import run_sync
        run_params = {k: v for k, v in params.items() if k != 'action'}
        return run_sync(run_params)

    if action == 'preview':
        from tools.query.service.execute import preview
        return preview(params)

    if action == 'task.get':
        from tools.query.service.task import task_get
        return task_get(params)

    if action == 'job.submit':
        from tools.query.service.jobs import job_submit
        return job_submit(params)

    if action == 'job.get':
        from tools.query.service.jobs import job_get
        return job_get(params)

    if action == 'job.list':
        from tools.query.service.jobs import job_list
        return job_list(params)

    if action == 'history.list':
        from tools.query.service.jobs import history_list
        return history_list(params)

    if action.startswith('strategy.'):
        from tools.query.service.strategy import run_strategy_action
        sub = action.split('.', 1)[1]
        return run_strategy_action(sub, params)

    raise ValueError(
        f'不支持的 action: {action}；允许: {", ".join(sorted(KNOWN_ACTIONS))}',
    )


def run(params: dict | None, *, run_id=None) -> dict:
    """兼容旧 tools.query.service.run 入口。"""
    return dispatch(params, run_id=run_id)
