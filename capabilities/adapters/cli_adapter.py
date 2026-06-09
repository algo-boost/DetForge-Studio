"""CLI 工具适配为 Capability。"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
from typing import Any

from capabilities.base import CapabilityResult, CapabilitySpec, RunContext

DEFAULT_TIMEOUT = int(os.environ.get('IISP_CLI_TIMEOUT', '3600'))
ALLOWED_PREFIXES = (
    'python', 'python3', 'iisp', 'coco-viz',
)


def _split_cli(cmd: str) -> list[str]:
    return shlex.split(str(cmd or '').strip())


def _validate_cli_command(cmd: str) -> None:
    parts = _split_cli(cmd)
    if not parts:
        raise ValueError('CLI 命令为空')
    exe = os.path.basename(parts[0]).lower()
    if not any(exe == p or exe.startswith(p) for p in ALLOWED_PREFIXES):
        raise ValueError(f'CLI 命令前缀不在白名单: {parts[0]}')


class CliCapabilityAdapter:
    """将 Manifest entry.cli 包装为可执行 Capability。"""

    def __init__(self, tool_id: str, label: str, cli_cmd: str, *,
                 params_schema: dict | None = None,
                 output_keys: list[str] | None = None,
                 description: str = ''):
        self.id = tool_id
        self._label = label
        self._cli_cmd = cli_cmd
        self._params_schema = params_schema or {}
        self._output_keys = output_keys or []
        self._description = description

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label=self._label,
            description=self._description,
            params_schema=self._params_schema,
            output_keys=self._output_keys,
            kind='cli',
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        _validate_cli_command(self._cli_cmd)
        payload = {
            'run_id': ctx.run_id,
            'step_id': ctx.step_id,
            'params': ctx.params,
            'inputs': ctx.inputs,
        }
        parts = _split_cli(self._cli_cmd)
        proc = subprocess.run(
            parts,
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            timeout=DEFAULT_TIMEOUT,
            cwd=os.environ.get('IISP_CLI_CWD') or None,
        )
        if proc.returncode != 0:
            err = (proc.stderr or proc.stdout or '').strip() or f'exit {proc.returncode}'
            return CapabilityResult(status='failed', reason=err)
        raw = (proc.stdout or '').strip()
        if not raw:
            return CapabilityResult(status='done', outputs={})
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            return CapabilityResult(status='failed', reason=f'CLI stdout 非 JSON: {e}')
        if not isinstance(data, dict):
            return CapabilityResult(status='failed', reason='CLI stdout 必须是 JSON 对象')
        status = str(data.get('status') or 'done')
        outputs = data.get('outputs') if isinstance(data.get('outputs'), dict) else data
        if data.get('skipped'):
            status = 'skipped'
            outputs = {**outputs, 'skipped': True}
        return CapabilityResult(status=status, outputs=outputs, reason=data.get('reason'))
