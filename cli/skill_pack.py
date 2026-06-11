"""SKILL validate / pack CLI 逻辑。"""
from __future__ import annotations

import json
from pathlib import Path

from capabilities.manifest import load_manifest, validate_manifest
from capabilities.skill_parser import parse_skill_file
from cli.tool_init import init_tool_from_skill


def validate_skill(skill_path: str) -> dict:
    parsed = parse_skill_file(skill_path)
    errors = list(parsed.get('warnings') or [])
    recommendations: list[str] = []
    body = parsed.get('body') or ''
    if '## 输入' not in body and '## Inputs' not in body.lower():
        recommendations.append('建议包含 ## 输入 章节')
    if '## 输出' not in body and '## Outputs' not in body.lower():
        recommendations.append('建议包含 ## 输出 章节')
    return {
        'success': bool(parsed.get('valid')) and not errors,
        'skill_path': skill_path,
        'name': parsed.get('name'),
        'errors': errors,
        'recommendations': recommendations,
        'inputs': parsed.get('inputs') or [],
        'outputs': parsed.get('output_keys') or [],
    }


def pack_skill(skill_path: str, out_dir: str, *, install: bool = False) -> dict:
    check = validate_skill(skill_path)
    if not check.get('success'):
        return {
            'success': False,
            'error': 'SKILL 校验未通过',
            'validate': check,
        }

    init_result = init_tool_from_skill(skill_path, out_dir)
    if not init_result.get('success'):
        return init_result

    manifest_path = Path(out_dir) / 'tool.manifest.json'
    data = load_manifest(str(manifest_path))
    data['contract_version'] = 'v1'
    data['version'] = data.get('version') or '0.1.0'
    entry = data.get('entry') or {}
    tool_id = data['id']
    entry['invoke'] = f'/v1/tools/{tool_id}/invoke'
    data['entry'] = entry
    manifest_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

    errs = validate_manifest(data, path=str(manifest_path))
    if errs:
        return {
            'success': False,
            'error': 'Manifest 校验失败',
            'manifest_errors': errs,
            'out_dir': out_dir,
        }

    installed = False
    if install:
        from capabilities.registry import init_registry
        reg = init_registry()
        n = reg.load_manifests()
        installed = n >= 0

    return {
        'success': True,
        'tool_id': tool_id,
        'out_dir': out_dir,
        'manifest_path': str(manifest_path),
        'validate': check,
        'installed': installed,
        'files': init_result.get('files') or [],
    }
