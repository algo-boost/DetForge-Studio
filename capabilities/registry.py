"""Capability Registry — 工具箱注册表。"""
from __future__ import annotations

import importlib
import logging
import threading
import time
from typing import Any

from capabilities.adapters.cli_adapter import CliCapabilityAdapter
from capabilities.adapters.http_adapter import HttpCapabilityAdapter
from capabilities.base import Capability, CapabilityResult, CapabilitySpec, RunContext
from capabilities.manifest import (
    discover_manifest_paths,
    load_manifest,
    manifest_to_spec,
    validate_manifest,
)

logger = logging.getLogger('iisp.capabilities.registry')

_registry: 'CapabilityRegistry | None' = None
_registry_lock = threading.Lock()

# 工作流 kind → Manifest tool id 别名（迁移期兼容）
KIND_ALIASES: dict[str, str] = {
    'query': 'query',
    'predict': 'predict',
    'curation_create': 'curation-create',
    'curation_export': 'curation-export',
    'gate_human': 'gate-human',
    'curation_import': 'curation-import',
    'curation_archive': 'curation-archive',
    'notify': 'notify',
    'manual_qc': 'manual-qc',
}


class FunctionCapability:
    """将函数包装为 Capability。"""

    def __init__(self, tool_id: str, label: str, fn, *,
                 params_schema: dict | None = None,
                 output_keys: list[str] | None = None,
                 description: str = '',
                 waiting_kinds: frozenset[str] | None = None):
        self.id = tool_id
        self._label = label
        self._fn = fn
        self._params_schema = params_schema or {}
        self._output_keys = output_keys or []
        self._description = description
        self._waiting_kinds = waiting_kinds or frozenset()

    def describe(self) -> CapabilitySpec:
        return CapabilitySpec(
            id=self.id,
            label=self._label,
            description=self._description,
            params_schema=self._params_schema,
            output_keys=self._output_keys,
        )

    def preview(self, ctx: RunContext) -> CapabilityResult | None:
        return None

    def execute(self, ctx: RunContext) -> CapabilityResult:
        legacy_ctx = {
            'run_id': ctx.run_id,
            'params': ctx.params,
            'steps': ctx.inputs.get('steps') or {},
            **{k: v for k, v in ctx.inputs.items() if k != 'steps'},
        }
        output = self._fn(ctx.params, legacy_ctx)
        if not isinstance(output, dict):
            output = {'result': output}
        if output.get('skipped'):
            return CapabilityResult(status='skipped', outputs=output, reason=output.get('reason'))
        if output.get('waiting') or self.id in self._waiting_kinds:
            return CapabilityResult(status='waiting_human', outputs=output)
        return CapabilityResult(status='done', outputs=output)


class CapabilityRegistry:
    def __init__(self):
        self._caps: dict[str, Capability] = {}
        self._manifests: dict[str, dict] = {}
        self._usage: dict[str, int] = {}

    def register(self, cap: Capability, manifest: dict | None = None) -> None:
        spec = cap.describe()
        self._caps[spec.id] = cap
        if manifest:
            self._manifests[spec.id] = manifest

    def register_function(self, tool_id: str, label: str, fn, **kwargs) -> None:
        self.register(FunctionCapability(tool_id, label, fn, **kwargs))

    def load_manifests(self) -> int:
        n = 0
        for path in discover_manifest_paths():
            try:
                data = load_manifest(path)
                data['_manifest_path'] = path
                errs = validate_manifest(data)
                if errs:
                    logger.warning('Manifest 校验失败 %s: %s', path, errs)
                    continue
                spec = manifest_to_spec(data)
                cap = self._capability_from_manifest(spec)
                if cap:
                    self.register(cap, spec)
                    n += 1
            except Exception as e:
                logger.warning('加载 Manifest 失败 %s: %s', path, e)
        return n

    def _capability_from_manifest(self, spec: dict) -> Capability | None:
        tool_id = spec['id']
        if tool_id in self._caps:
            return None
        kind = spec.get('kind') or 'capability'
        entry = spec.get('entry') or {}
        if kind == 'cli':
            cli = entry.get('cli')
            if not cli:
                return None
            return CliCapabilityAdapter(
                tool_id, spec['label'], cli,
                params_schema=spec.get('params_schema'),
                output_keys=spec.get('outputs'),
                description=spec.get('description') or '',
            )
        if kind == 'blueprint':
            url = entry.get('blueprint')
            if not url:
                return None
            return HttpCapabilityAdapter(
                tool_id, spec['label'], url,
                params_schema=spec.get('params_schema'),
                description=spec.get('description') or '',
            )
        cap_path = entry.get('capability')
        if cap_path and ':' in cap_path:
            mod_name, cls_name = cap_path.split(':', 1)
            mod = importlib.import_module(mod_name)
            cls = getattr(mod, cls_name)
            return cls()
        return None

    def resolve_id(self, kind_or_id: str) -> str:
        k = str(kind_or_id or '').strip()
        return KIND_ALIASES.get(k, k)

    def get(self, kind_or_id: str) -> Capability | None:
        tid = self.resolve_id(kind_or_id)
        return self._caps.get(tid)

    def list_tools(self) -> list[dict]:
        out = []
        for cap in self._caps.values():
            spec = cap.describe()
            manifest = self._manifests.get(spec.id, {})
            out.append({
                'id': spec.id,
                'label': spec.label,
                'description': spec.description,
                'kind': manifest.get('kind') or getattr(spec, 'kind', 'capability'),
                'version': manifest.get('version'),
                'params_schema': spec.params_schema,
                'inputs': manifest.get('inputs') or spec.required_inputs,
                'outputs': manifest.get('outputs') or spec.output_keys,
                'artifacts': manifest.get('artifacts') or [],
                'usage_count': self._usage.get(spec.id, 0),
                'skill_source': manifest.get('skill_source'),
                'manifest_path': manifest.get('manifest_path'),
            })
        return sorted(out, key=lambda x: x['id'])

    def execute(self, kind_or_id: str, ctx: RunContext) -> CapabilityResult:
        tid = self.resolve_id(kind_or_id)
        cap = self.get(tid)
        if not cap:
            raise ValueError(f'未注册的工具/Capability: {kind_or_id}')
        self._usage[tid] = self._usage.get(tid, 0) + 1
        t0 = time.monotonic()
        try:
            result = cap.execute(ctx)
            logger.info('capability %s done in %.2fs status=%s', tid, time.monotonic() - t0, result.status)
            return result
        except Exception as e:
            logger.exception('capability %s failed', tid)
            return CapabilityResult(status='failed', reason=str(e))

    def usage_stats(self) -> dict[str, int]:
        return dict(self._usage)


def get_registry() -> CapabilityRegistry:
    global _registry
    if _registry is None:
        with _registry_lock:
            if _registry is None:
                _registry = CapabilityRegistry()
    return _registry


def init_registry() -> CapabilityRegistry:
    """注册内置 Capability 并加载 Manifest。"""
    from capabilities.builtins import register_builtin_capabilities

    reg = get_registry()
    register_builtin_capabilities(reg)
    reg.load_manifests()
    return reg
