"""Agent / MCP 共享逻辑（IDE 无关）。"""
from __future__ import annotations

import json
import os
from typing import Any

from orchestration.agent_context import build_agent_context
from orchestration.loader import discover_pipelines
from orchestration.pipeline_validate import validate_pipeline_path, validate_pipeline_text


def _agent_invoke_allowed() -> bool:
    env = os.environ.get('IISP_ENV', 'dev').lower()
    allow = os.environ.get('IISP_AGENT_ALLOW_INVOKE', '0').lower()
    return env == 'dev' and allow in ('1', 'true', 'yes')


def list_tools_for_agent(*, tag: str | None = None) -> dict[str, Any]:
    from capabilities.registry import init_registry

    reg = init_registry()
    tools = reg.list_tools()
    if tag:
        needle = tag.strip().lower()
        tools = [
            t for t in tools
            if needle in str(t.get('id') or '').lower()
            or needle in str(t.get('label') or '').lower()
            or needle in [str(x).lower() for x in (t.get('tags') or [])]
        ]
    slim = []
    for t in tools:
        slim.append({
            'id': t['id'],
            'label': t.get('label') or t['id'],
            'description': t.get('description') or '',
            'outputs': t.get('outputs') or [],
            'params_schema': t.get('params_schema') or {},
            'tags': t.get('tags') or [],
        })
    return {'tools': slim}


def get_tool_manifest(tool_id: str) -> dict[str, Any]:
    from capabilities.manifest import discover_manifest_paths, load_manifest

    tid = str(tool_id or '').strip()
    for path in discover_manifest_paths():
        try:
            data = load_manifest(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if str(data.get('id') or '') == tid:
            data = dict(data)
            data['_manifest_path'] = path
            return data
    raise FileNotFoundError(f'工具 Manifest 未找到: {tool_id}')


def validate_manifest_for_agent(*, path: str | None = None, json_text: str | None = None) -> dict:
    from capabilities.manifest import load_manifest, validate_manifest

    if path:
        data = load_manifest(path)
        errors = validate_manifest(data, path=path)
        return {'valid': len(errors) == 0, 'errors': errors, 'id': data.get('id')}
    if json_text:
        data = json.loads(json_text)
        if not isinstance(data, dict):
            return {'valid': False, 'errors': ['Manifest 必须是 JSON 对象'], 'id': None}
        errors = validate_manifest(data)
        return {'valid': len(errors) == 0, 'errors': errors, 'id': data.get('id')}
    return {'valid': False, 'errors': ['需要 path 或 json'], 'id': None}


def validate_pipeline_for_agent(*, path: str | None = None, yaml_text: str | None = None) -> dict:
    if path:
        return validate_pipeline_path(path)
    if yaml_text:
        return validate_pipeline_text(yaml_text)
    return {'valid': False, 'errors': ['需要 path 或 yaml'], 'id': None, 'engine': None}


def list_pipelines_for_agent(*, catalog: str = 'repo') -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    if catalog in ('repo', 'all'):
        for p in discover_pipelines():
            rows.append({
                'id': p.get('id'),
                'path': p.get('_path'),
                'label': p.get('name') or p.get('id'),
                'engine': 'legacy',
                'valid': p.get('_valid'),
            })
    return {'pipelines': rows}


def init_tool_from_skill_for_agent(skill_path: str, out_dir: str) -> dict[str, Any]:
    from cli.tool_init import init_tool_from_skill

    return init_tool_from_skill(skill_path, out_dir)


def invoke_tool_for_agent(
    tool_id: str,
    *,
    params: dict | None = None,
    run_id: str = 'mcp-agent',
    step_id: str = 'main',
) -> dict[str, Any]:
    if not _agent_invoke_allowed():
        raise PermissionError(
            'iisp_invoke 已禁用：设置 IISP_ENV=dev 且 IISP_AGENT_ALLOW_INVOKE=1'
        )
    from capabilities.base import RunContext
    from capabilities.registry import init_registry
    from server.gateway.contract import result_to_v1

    reg = init_registry()
    ctx = RunContext(
        run_id=run_id,
        step_id=step_id,
        params=params or {},
        inputs={},
    )
    result = reg.execute(tool_id, ctx)
    return result_to_v1(result)
