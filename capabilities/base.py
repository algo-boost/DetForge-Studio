"""Capability 契约类型（对齐 docs/ARCHITECTURE_DECOUPLED.md §5）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class Artifact:
    kind: str
    uri: str
    meta: dict = field(default_factory=dict)


@dataclass
class CapabilitySpec:
    id: str
    label: str
    description: str = ''
    params_schema: dict = field(default_factory=dict)
    required_inputs: list[str] = field(default_factory=list)
    output_keys: list[str] = field(default_factory=list)
    kind: str = 'capability'


@dataclass
class RunContext:
    run_id: str | int | None
    step_id: str | None
    params: dict
    inputs: dict
    services: Any = None


@dataclass
class CapabilityResult:
    status: str = 'done'
    outputs: dict = field(default_factory=dict)
    artifacts: list[Artifact] = field(default_factory=list)
    reason: str | None = None

    @property
    def skipped(self) -> bool:
        return self.status == 'skipped' or bool(self.outputs.get('skipped'))

    def to_step_output(self) -> dict:
        """转为 workflow_steps 兼容的 dict 输出。"""
        out = dict(self.outputs)
        if self.status == 'skipped' and 'skipped' not in out:
            out['skipped'] = True
        if self.status == 'waiting_human':
            out['waiting'] = True
        return out


class Capability(Protocol):
    id: str

    def describe(self) -> CapabilitySpec: ...
    def execute(self, ctx: RunContext) -> CapabilityResult: ...
    def preview(self, ctx: RunContext) -> CapabilityResult | None: ...
