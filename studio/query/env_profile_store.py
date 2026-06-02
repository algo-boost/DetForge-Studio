"""环境变量模版（Profile）持久化：JSON 文件存储，供查询与回跑共用。"""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime

from studio.paths import PROJECT_ROOT
from studio.query.env_context import extract_template_vars
from studio.query.strategy_env_schema import merge_strategy_env_schema
from studio.query.strategy_loader import get_all_strategies, get_all_templates
from studio.flow.flow_compiler import normalize_strategy

ENV_PROFILES_DIR = os.path.join(PROJECT_ROOT, 'env_profiles')

_SAFE_ID = re.compile(r'^[a-zA-Z0-9_-]+$')


def _ensure_dir():
    os.makedirs(ENV_PROFILES_DIR, exist_ok=True)


def _profile_path(profile_id: str) -> str:
    if not _SAFE_ID.match(profile_id or ''):
        raise ValueError('模版 id 仅允许字母、数字、下划线、连字符')
    return os.path.join(ENV_PROFILES_DIR, f'{profile_id}.json')


def _normalize_var_row(row: dict) -> dict | None:
    if not isinstance(row, dict):
        return None
    key = str(row.get('key') or '').strip().upper()
    if not key:
        return None
    return {
        'key': key,
        'label': str(row.get('label') or key).strip(),
        'type': str(row.get('type') or 'text').strip().lower(),
        'value': '' if row.get('value') is None else str(row.get('value')),
        'description': row.get('description') or '',
    }


def normalize_profile(data: dict, profile_id: str | None = None) -> dict:
    data = copy.deepcopy(data or {})
    pid = (profile_id or data.get('id') or '').strip()
    if not pid:
        raise ValueError('模版 id 不能为空')
    now = datetime.now().isoformat()
    vars_in = data.get('vars')
    rows = []
    if isinstance(vars_in, dict):
        for k, v in vars_in.items():
            row = _normalize_var_row({'key': k, 'value': v})
            if row:
                rows.append(row)
    elif isinstance(vars_in, list):
        for item in vars_in:
            row = _normalize_var_row(item)
            if row:
                rows.append(row)

    hints = data.get('strategy_hints') or data.get('linked_strategies') or []
    if isinstance(hints, str):
        hints = [h.strip() for h in hints.split(',') if h.strip()]

    return {
        'id': pid,
        'name': str(data.get('name') or pid).strip(),
        'description': str(data.get('description') or '').strip(),
        'strategy_hints': [str(h).strip() for h in hints if str(h).strip()],
        'vars': rows,
        'created_at': data.get('created_at') or now,
        'updated_at': now,
    }


def profile_to_env(profile: dict | None) -> dict[str, str]:
    """Profile → 执行用 env 字典。"""
    out = {}
    if not profile:
        return out
    for row in profile.get('vars') or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get('key') or '').strip().upper()
        val = row.get('value')
        if not key or val is None or str(val).strip() == '':
            continue
        out[key] = str(val).strip()
    return out


def list_profiles():
    _ensure_dir()
    items = []
    for fname in sorted(os.listdir(ENV_PROFILES_DIR)):
        if not fname.endswith('.json'):
            continue
        try:
            with open(os.path.join(ENV_PROFILES_DIR, fname), 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('id'):
                items.append(data)
        except Exception:
            pass
    items.sort(key=lambda x: x.get('updated_at') or '', reverse=True)
    return items


def get_profile(profile_id: str):
    path = _profile_path(profile_id)
    if not os.path.isfile(path):
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_profile(data: dict):
    _ensure_dir()
    existing = get_profile(data.get('id', '')) if data.get('id') else None
    profile = normalize_profile(data, data.get('id'))
    if existing and existing.get('created_at'):
        profile['created_at'] = existing['created_at']
    path = _profile_path(profile['id'])
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)
    return profile


def delete_profile(profile_id: str) -> bool:
    path = _profile_path(profile_id)
    if os.path.isfile(path):
        os.remove(path)
        return True
    return False


def suggest_vars(strategy_ids=None):
    """从策略 env_schema / 模板推断建议变量行。"""
    strategies = get_all_strategies()
    templates = get_all_templates()
    merged = {}
    for sid in strategy_ids or []:
        raw = strategies.get(sid)
        if not raw:
            continue
        strategy = normalize_strategy(dict(raw), templates)
        for row in merge_strategy_env_schema(strategy, templates):
            key = row['key']
            if key not in merged:
                merged[key] = {
                    'key': key,
                    'label': row.get('label') or key,
                    'type': row.get('type') or 'text',
                    'value': '' if row.get('default') is None else str(row.get('default')),
                    'description': row.get('description') or '',
                    'from_strategies': [sid],
                }
            elif sid not in merged[key]['from_strategies']:
                merged[key]['from_strategies'].append(sid)
    return list(merged.values())
