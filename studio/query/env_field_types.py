"""策略环境变量字段类型定义与规范化。"""
from __future__ import annotations

from typing import Any

# 支持的可调参数类型
ENV_FIELD_TYPES = frozenset({
    'text',       # 文本
    'number',     # 数字
    'datetime',   # 时间字符串 YYYY-MM-DD HH:MM:SS
    'select',     # 下拉单选
    'multiselect',  # 下拉多选（存 env 为逗号分隔）
})

ENV_FIELD_TYPE_LABELS = {
    'text': '文本',
    'number': '数字',
    'datetime': '时间字符串',
    'select': '下拉单选',
    'multiselect': '下拉多选',
}


def normalize_field_type(raw: str | None) -> str:
    t = str(raw or 'text').strip().lower()
    aliases = {
        'string': 'text',
        'str': 'text',
        'int': 'number',
        'float': 'number',
        'time': 'datetime',
        'date': 'datetime',
        'select_single': 'select',
        'single_select': 'select',
        'multi_select': 'multiselect',
        'multi-select': 'multiselect',
    }
    t = aliases.get(t, t)
    return t if t in ENV_FIELD_TYPES else 'text'


def normalize_options(raw) -> list[dict[str, str]]:
    """规范 options 为 [{value, label}, ...]。"""
    if not raw:
        return []
    items = raw if isinstance(raw, list) else []
    out: list[dict[str, str]] = []
    for item in items:
        if isinstance(item, dict):
            val = str(item.get('value', item.get('id', ''))).strip()
            if not val:
                continue
            out.append({
                'value': val,
                'label': str(item.get('label') or val).strip(),
            })
        else:
            s = str(item).strip()
            if s:
                out.append({'value': s, 'label': s})
    return out


def normalize_env_field_row(row: dict | None) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    key = str(row.get('key') or '').strip().upper()
    if not key:
        return None
    ftype = normalize_field_type(row.get('type'))
    out: dict[str, Any] = {
        'key': key,
        'label': row.get('label') or key,
        'type': ftype,
        'default': row.get('default'),
        'placeholder': row.get('placeholder'),
        'stage': row.get('stage'),
        'description': row.get('description'),
    }
    opts = normalize_options(row.get('options'))
    if opts:
        out['options'] = opts
    if row.get('min') is not None:
        out['min'] = row['min']
    if row.get('max') is not None:
        out['max'] = row['max']
    if row.get('step') is not None:
        out['step'] = row['step']
    return out
