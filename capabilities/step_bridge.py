"""workflow_steps ↔ Capability Registry 桥接。"""
from __future__ import annotations

import os

from capabilities.base import RunContext
from capabilities.registry import get_registry


def use_registry() -> bool:
    return os.environ.get('IISP_USE_REGISTRY', '1').lower() in ('1', 'true', 'yes')


def execute_via_registry(kind: str, params: dict, context: dict):
    """通过 Registry 执行步骤，返回与 STEP_HANDLERS 兼容的 dict。"""
    reg = get_registry()
    steps = dict(context.get('steps') or {})
    ctx = RunContext(
        run_id=context.get('run_id'),
        step_id=context.get('step_id'),
        params=params,
        inputs={'steps': steps, **{k: v for k, v in context.items() if k not in ('steps', 'params')}},
    )
    result = reg.execute(kind, ctx)
    return result.to_step_output()
