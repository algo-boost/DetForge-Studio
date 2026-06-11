"""query-strategy 兼容别名 → query dispatch。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext
from tools.query.capability import QueryCapability


class QueryStrategyAliasCapability(QueryCapability):
    """已合并入 query；保留 tool_id 供旧脚本与 Gateway 路径兼容。"""

    id = 'query-strategy'

    def describe(self) -> CapabilitySpec:
        spec = super().describe()
        return CapabilitySpec(
            id=self.id,
            label='查询策略（兼容别名）',
            description='请改用 query 工具 action=strategy.*；本 id 将废弃',
            params_schema=spec.params_schema,
            output_keys=spec.output_keys,
            kind='hybrid',
        )

    def execute(self, ctx: RunContext) -> CapabilityResult:
        params = dict(ctx.params or {})
        if params.get('action') and not str(params['action']).startswith('strategy.'):
            legacy = str(params['action']).strip().lower()
            if legacy in ('list', 'get', 'variables', 'validate', 'save', 'delete'):
                params['action'] = f'strategy.{legacy}'
        elif not params.get('action'):
            params['action'] = 'strategy.list'
        return super().execute(
            RunContext(
                run_id=ctx.run_id,
                step_id=ctx.step_id,
                params=params,
                inputs=ctx.inputs,
                services=ctx.services,
            ),
        )
