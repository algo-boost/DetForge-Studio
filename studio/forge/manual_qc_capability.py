"""Manual QC Capability 包装。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext
from studio.forge import forge_manual_qc as mq


class ManualQcCapability:
    id = 'manual-qc'

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label='人工质检',
            description='按 SN 查询平台缺陷图记录',
            params_schema={
                'type': 'object',
                'properties': {
                    'sn': {'type': 'string'},
                    'limit': {'type': 'integer', 'default': 50},
                },
                'required': ['sn'],
            },
            output_keys=['records', 'match_status', 'count'],
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        sn = str(ctx.params.get('sn') or '').strip()
        limit = int(ctx.params.get('limit') or 50)
        records = mq.find_platform_records_by_sn(sn, limit=limit)
        status = mq._match_status(records)
        return CapabilityResult(
            status='done',
            outputs={
                'records': records,
                'match_status': status,
                'count': len(records),
                'sn': sn,
            },
        )
