"""Tool Manifest 加载与校验。"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from studio.paths import APP_ROOT

REQUIRED_FIELDS = ('id', 'version', 'label', 'kind', 'entry')
VALID_KINDS = frozenset({'capability', 'cli', 'blueprint', 'hybrid'})


def manifest_search_roots() -> list[str]:
    roots = [
        os.path.join(APP_ROOT, 'tools'),
        os.path.join(APP_ROOT, 'packages'),
        os.path.join(APP_ROOT, 'studio'),
        APP_ROOT,
    ]
    return [r for r in roots if os.path.isdir(r)]


def discover_manifest_paths() -> list[str]:
    found: list[str] = []
    for root in manifest_search_roots():
        for path in Path(root).rglob('tool.manifest.json'):
            if path.is_file():
                found.append(str(path))
    return sorted(set(found))


def load_manifest(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f'Manifest 必须是 JSON 对象: {path}')
    return data


def validate_manifest(data: dict, *, path: str = '') -> list[str]:
    errors: list[str] = []
    for field in REQUIRED_FIELDS:
        if not data.get(field):
            errors.append(f'缺少必填字段: {field}')
    kind = str(data.get('kind') or '')
    if kind and kind not in VALID_KINDS:
        errors.append(f'kind 无效: {kind}，允许 {sorted(VALID_KINDS)}')
    entry = data.get('entry')
    if isinstance(entry, dict):
        if kind in ('capability', 'hybrid') and not entry.get('capability'):
            errors.append('kind=capability/hybrid 需要 entry.capability')
        if kind in ('cli', 'hybrid') and not entry.get('cli'):
            errors.append('kind=cli/hybrid 需要 entry.cli')
    elif entry is not None:
        errors.append('entry 必须是对象')
    mid = str(data.get('id') or '')
    if mid and not mid.replace('-', '').replace('_', '').isalnum():
        errors.append('id 建议仅含字母、数字、连字符、下划线')
    return errors


def manifest_to_spec(data: dict) -> dict[str, Any]:
    return {
        'id': data['id'],
        'label': data.get('label') or data['id'],
        'description': data.get('description') or '',
        'version': data.get('version') or '0.0.0',
        'kind': data.get('kind') or 'capability',
        'params_schema': data.get('params_schema') or {},
        'inputs': data.get('inputs') or [],
        'outputs': data.get('outputs') or [],
        'artifacts': data.get('artifacts') or [],
        'entry': data.get('entry') or {},
        'skill_source': data.get('skill_source'),
        'manifest_path': data.get('_manifest_path'),
        'tags': data.get('tags') or [],
    }
