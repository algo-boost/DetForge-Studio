"""延锋门板查询 — 从 SKILL 转化的示范工具包。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext
from studio.forge import workflow_steps as ws


class YfDoorPanelQueryCapability:
    id = 'yf-door-panel-query'

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label='延锋门板查询',
            description='按策略查询延锋门板平台数据',
            params_schema={
                'type': 'object',
                'properties': {
                    'strategy_id': {'type': 'string'},
                    'time_window': {'type': 'object'},
                    'data_source': {'type': 'string', 'default': 'detail'},
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
