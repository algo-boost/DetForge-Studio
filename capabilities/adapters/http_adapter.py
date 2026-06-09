"""Blueprint HTTP 远程调用适配器（预留）。"""
from __future__ import annotations

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext


class HttpCapabilityAdapter:
    """未来用于独立 Blueprint 微服务的 HTTP bridge。"""

    def __init__(self, tool_id: str, label: str, base_url: str, *,
                 params_schema: dict | None = None,
                 description: str = ''):
        self.id = tool_id
        self._label = label
        self._base_url = base_url.rstrip('/')
        self._params_schema = params_schema or {}
        self._description = description

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label=self._label,
            description=self._description,
            params_schema=self._params_schema,
            kind='blueprint',
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        return CapabilityResult(
            status='failed',
            reason=f'HTTP adapter 尚未实现: {self._base_url}',
        )
