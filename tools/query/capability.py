"""查询工具 Capability — 单工具 action 路由。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext
from lib.iisp_cli.contract import artifacts_from_outputs
from tools.query.service.dispatch import dispatch, resolve_action


class QueryCapability:
    id = 'query'

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label='数据查询',
            description='查询域统一工具：执行、结果、历史、策略（action 路由）',
            params_schema={
                'type': 'object',
                'properties': {
                    'action': {
                        'type': 'string',
                        'description': 'execute|preview|task.get|job.*|history.list|strategy.*；省略且含 strategy_id 时为 execute',
                    },
                    'strategy_id': {'type': 'string'},
                    'time_window': {'type': 'object'},
                    'data_source': {'type': 'string'},
                    'task_id': {'type': 'string'},
                    'job_id': {'type': 'string'},
                    'strategy': {'type': 'object'},
                    'env': {'type': 'object'},
                },
            },
            output_keys=['action', 'task_id', 'row_count', 'count', 'strategies', 'strategy', 'jobs'],
            kind='hybrid',
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        try:
            out = dispatch(ctx.params, run_id=ctx.run_id)
        except Exception as exc:  # noqa: BLE001
            return CapabilityResult(status='failed', reason=str(exc))
        action = resolve_action(ctx.params)
        if action == 'execute' and out.get('skipped'):
            return CapabilityResult(status='skipped', outputs=out, reason=out.get('reason'))
        artifacts = artifacts_from_outputs(out, ['csv']) if action == 'execute' else []
        return CapabilityResult(status='done', outputs=out, artifacts=artifacts)
