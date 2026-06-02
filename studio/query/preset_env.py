"""预设环境变量：时段默认值、schema 补全与执行前填充。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from studio.query.strategy_env_schema import TIME_ENV_FIELDS

_TIME_VAR_KEYS = frozenset({'START_TIME', 'END_TIME'})


def _pad(n: int) -> str:
    return str(n).zfill(2)


def format_sql_datetime(dt: datetime) -> str:
    return dt.strftime('%Y-%m-%d %H:%M:%S')


def time_range_for_preset(preset: str = 'today') -> tuple[str, str]:
    """快捷时段 → (START_TIME, END_TIME) SQL 格式字符串。"""
    now = datetime.now().replace(second=0, microsecond=0)
    end = now
    start = now

    if preset == 'today':
        start = start.replace(hour=0, minute=0)
    elif preset == 'yesterday':
        start = (start - timedelta(days=1)).replace(hour=0, minute=0)
        end = (end - timedelta(days=1)).replace(hour=23, minute=59)
    elif preset == '7days':
        start = (start - timedelta(days=7)).replace(hour=0, minute=0)
    elif preset == '30days':
        start = (start - timedelta(days=30)).replace(hour=0, minute=0)
    else:
        start = (start - timedelta(days=7)).replace(hour=0, minute=0)

    return format_sql_datetime(start), format_sql_datetime(end)


def schema_has_time_vars(schema: list[dict] | None) -> bool:
    if not schema:
        return False
    keys = {str(r.get('key', '')).upper() for r in schema if isinstance(r, dict)}
    return bool(keys & _TIME_VAR_KEYS)


def ensure_time_env_schema(schema: list[dict] | None, *, sql_template: str = '') -> list[dict]:
    """SQL 含时段占位符时自动补全 START_TIME / END_TIME schema。"""
    from studio.query.strategy_env_schema import merge_env_schema_rows

    sql = sql_template or ''
    needs = '${START_TIME}' in sql or '${END_TIME}' in sql or 'get_env' in sql.lower()
    if not needs and schema_has_time_vars(schema):
        return list(schema or [])
    if not needs:
        return list(schema or [])
    return merge_env_schema_rows(schema, TIME_ENV_FIELDS)


def fill_time_env_defaults(
    env: dict[str, str] | None,
    *,
    preset: str = 'today',
    schema: list[dict] | None = None,
) -> dict[str, str]:
    """空缺的 START_TIME / END_TIME 用快捷时段填充。"""
    out = dict(env or {})
    if not schema_has_time_vars(schema) and not (out.get('START_TIME') or out.get('END_TIME')):
        sql_keys = _TIME_VAR_KEYS
        if not any(k in out for k in sql_keys):
            return out
    start, end = time_range_for_preset(preset)
    if not str(out.get('START_TIME', '')).strip():
        out['START_TIME'] = start
    if not str(out.get('END_TIME', '')).strip():
        out['END_TIME'] = end
    return out


def apply_env_schema_defaults(
    env: dict[str, str] | None,
    schema: list[dict] | None,
    *,
    time_preset: str = 'today',
) -> dict[str, str]:
    """按 schema default + 时段预设合并环境变量。"""
    from studio.query.env_context import normalize_env_dict

    out = normalize_env_dict(env)
    for row in schema or []:
        if not isinstance(row, dict):
            continue
        key = str(row.get('key', '')).strip().upper()
        if not key or str(out.get(key, '')).strip():
            continue
        default = row.get('default')
        if default is not None and str(default).strip() != '':
            out[key] = str(default).strip()
    if schema_has_time_vars(schema):
        out = fill_time_env_defaults(out, preset=time_preset, schema=schema)
    return out
