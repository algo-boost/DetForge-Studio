"""Query Capability 包装。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext
from studio.forge import workflow_steps as ws


class QueryCapability:
    id = 'query'

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label='数据查询',
            description='按策略查询平台数据并创建查询任务',
            params_schema={
                'type': 'object',
                'properties': {
                    'strategy_id': {'type': 'string'},
                    'time_window': {'type': 'object'},
                    'data_source': {'type': 'string'},
                },
                'required': ['strategy_id'],
            },
            output_keys=['task_id', 'row_count', 'count'],
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        legacy = {'run_id': ctx.run_id, 'steps': (ctx.inputs or {}).get('steps') or {}}
        out = ws.run_query_step(ctx.params, legacy)
        if out.get('skipped'):
            return CapabilityResult(status='skipped', outputs=out, reason=out.get('reason'))
        return CapabilityResult(status='done', outputs=out)
