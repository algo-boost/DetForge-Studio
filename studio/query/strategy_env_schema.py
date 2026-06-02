"""策略环境变量 schema：与 python_presets 勾选、Flow 块、SQL 占位符合并。"""
from __future__ import annotations

from typing import Any

from studio.query.env_context import AUTO_RUNTIME_VARS, extract_template_vars
from studio.query.python_preset_registry import (
    active_presets_for_env_schema,
    flow_node_preset_id,
    inactive_preset_env_keys,
    preset_env_schema_for_active,
)


def _pipeline_step_env_allowed(step: dict, templates: dict, active_presets: list[str]) -> bool:
    tpl = templates.get(step.get('template_id') or '') or {}
    gid = tpl.get('preset_group')
    if not gid:
        return True
    return gid in active_presets


def collect_pipeline_env_schema(
    pipeline: list | None,
    templates: dict | None,
    strategy: dict | None = None,
) -> list[dict[str, Any]]:
    """从 process_pipeline 步骤合并块模板 env 字段。"""
    from studio.flow.process_pipeline import normalize_process_pipeline

    templates = templates or {}
    strategy = strategy or {}
    active = active_presets_for_env_schema(strategy)
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for step in normalize_process_pipeline(pipeline, templates):
        if not _pipeline_step_env_allowed(step, templates, active):
            continue
        tpl_id = step.get('template_id') or ''
        tpl = templates.get(tpl_id) or {}
        for row in params_schema_to_env_fields(tpl.get('params_schema')):
            k = row['key']
            if k not in seen:
                seen.add(k)
                fields.append(row)
    return fields

# 预设策略常用时段参数（写入 env_schema，由查询页工具栏同步赋值）
TIME_ENV_FIELDS = [
    {
        'key': 'START_TIME',
        'label': '开始时间',
        'type': 'datetime',
        'placeholder': 'YYYY-MM-DD HH:MM:SS',
        'description': 'SQL/Python 使用 ${START_TIME} 或 get_env("START_TIME")',
    },
    {
        'key': 'END_TIME',
        'label': '结束时间',
        'type': 'datetime',
        'placeholder': 'YYYY-MM-DD HH:MM:SS',
        'description': 'SQL/Python 使用 ${END_TIME} 或 get_env("END_TIME")',
    },
]

_PARAM_ENV_ALIASES = {
    'max_rows': 'SAMPLE_SIZE',
    'random_seed': 'RANDOM_SEED',
}


def _norm_key(key: str) -> str:
    return str(key or '').strip().upper()


def _schema_row(key: str, field: dict) -> dict[str, Any] | None:
    from studio.query.env_field_types import normalize_env_field_row, normalize_field_type

    raw = field.get('type') or 'text'
    if raw in ('range', 'rules_table'):
        mapped = 'text'
    else:
        mapped = normalize_field_type(raw)
    return normalize_env_field_row({
        'key': _norm_key(key),
        'label': field.get('label') or key,
        'type': mapped,
        'default': field.get('default'),
        'placeholder': field.get('placeholder'),
        'description': field.get('description'),
        'options': field.get('options'),
        'min': field.get('min'),
        'max': field.get('max'),
        'step': field.get('step'),
        'stage': field.get('stage'),
    })


def params_schema_to_env_fields(params_schema: list | None) -> list[dict[str, Any]]:
    """块模板 params_schema → 环境变量字段（env_key 优先，否则常见别名）。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for field in params_schema or []:
        if not isinstance(field, dict):
            continue
        env_key = field.get('env_key') or _PARAM_ENV_ALIASES.get(field.get('key', ''))
        if env_key:
            key = _norm_key(env_key)
        else:
            raw = str(field.get('key') or '').strip()
            if not raw:
                continue
            key = _norm_key(raw) if raw.isupper() else _norm_key(raw)
        if not key or key in seen or key in AUTO_RUNTIME_VARS:
            continue
        seen.add(key)
        row = _schema_row(key, field)
        if row:
            out.append(row)
    return out


def _flow_node_env_allowed(node: dict, active_presets: list[str]) -> bool:
    """该 Flow 节点是否允许向 env_schema 贡献参数（须对应预设已勾选）。"""
    need = flow_node_preset_id(node)
    if need is None:
        return True
    return need in active_presets


def collect_flow_env_schema(
    flow: dict | None,
    templates: dict | None,
    strategy: dict | None = None,
) -> list[dict[str, Any]]:
    """从 Flow 引用的块收集 env；仅合并已勾选预设包对应块（如 random_sample→采样）。"""
    flow = flow or {}
    templates = templates or {}
    strategy = strategy or {}
    active = active_presets_for_env_schema(strategy)
    fields: list[dict[str, Any]] = []
    seen: set[str] = set()
    for node in flow.get('nodes') or []:
        if not isinstance(node, dict):
            continue
        if not _flow_node_env_allowed(node, active):
            for branch in ('body', 'then', 'else'):
                sub = {'version': 2, 'nodes': node.get(branch) or []}
                fields.extend(collect_flow_env_schema(sub, templates, strategy))
            continue
        tpl_id = node.get('template_id') or ''
        if not tpl_id and str(node.get('type', '')).startswith('template.'):
            tpl_id = str(node['type']).replace('template.', '', 1)
        if tpl_id and tpl_id in templates:
            for row in params_schema_to_env_fields(templates[tpl_id].get('params_schema')):
                k = row['key']
                if k not in seen:
                    seen.add(k)
                    fields.append(row)
        for branch in ('body', 'then', 'else'):
            sub = {'version': 2, 'nodes': node.get(branch) or []}
            fields.extend(collect_flow_env_schema(sub, templates, strategy))
    return fields


def merge_env_schema_rows(*layers: list[dict] | None) -> list[dict[str, Any]]:
    """按 key 合并多层 schema，先出现的定义优先。"""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for layer in layers:
        for row in layer or []:
            if not isinstance(row, dict):
                continue
            key = _norm_key(row.get('key'))
            if not key or key in seen:
                continue
            seen.add(key)
            out.append({**row, 'key': key})
    return out


def filter_env_schema_by_presets(
    rows: list[dict[str, Any]] | None,
    strategy: dict | None,
) -> list[dict[str, Any]]:
    """剔除未勾选预设包专属的环境变量。"""
    strategy = strategy or {}
    active = active_presets_for_env_schema(strategy)
    blocked = inactive_preset_env_keys(active)
    return [r for r in (rows or []) if _norm_key(r.get('key')) not in blocked]


def strategy_needs_sampling_env(strategy: dict | None, templates: dict | None = None) -> bool:
    """是否展示采样参数（仅看活跃预设是否含 sampling）。"""
    return 'sampling' in active_presets_for_env_schema(strategy or {})


# 兼容旧引用
def _sampling_env_keys() -> frozenset[str]:
    from studio.query.python_preset_registry import preset_env_keys_map
    return preset_env_keys_map().get('sampling', frozenset())


SAMPLING_ENV_KEYS = _sampling_env_keys()


def sync_env_schema_with_capabilities(strategy: dict | None, templates: dict | None = None) -> list[dict[str, Any]]:
    """按 python_presets 裁剪/补全 env_schema（保存前调用）。"""
    return merge_strategy_env_schema(strategy, templates)


def merge_strategy_env_schema(strategy: dict | None, templates: dict | None = None) -> list[dict[str, Any]]:
    """
    策略 env_schema + Flow + SQL 推断，最终仅保留：
    - 时段等通用项
    - 已勾选 python_presets 的默认参数
    - 非预设专属的自定义项
    """
    from studio.query.env_context import resolve_strategy_env_schema
    from studio.query.preset_env import ensure_time_env_schema

    strategy = strategy or {}
    active = active_presets_for_env_schema(strategy)
    blocked = inactive_preset_env_keys(active)

    base = filter_env_schema_by_presets(resolve_strategy_env_schema(strategy), strategy)
    base = ensure_time_env_schema(base, sql_template=strategy.get('sql_template') or '')
    pipeline_rows = filter_env_schema_by_presets(
        collect_pipeline_env_schema(strategy.get('process_pipeline'), templates, strategy),
        strategy,
    )
    flow_rows = filter_env_schema_by_presets(
        collect_flow_env_schema(strategy.get('flow'), templates, strategy) if templates else [],
        strategy,
    )
    inferred = [
        {
            'key': k,
            'label': k,
            'type': 'datetime' if k in ('START_TIME', 'END_TIME') else 'text',
        }
        for k in extract_template_vars(
            strategy.get('sql_template'),
            strategy.get('python_code'),
            strategy.get('filter_rules_code'),
            strategy.get('sample_code'),
        )
        if k not in AUTO_RUNTIME_VARS and k not in blocked
    ]
    preset_rows = preset_env_schema_for_active(active)
    merged = merge_env_schema_rows(base, pipeline_rows, flow_rows, inferred, preset_rows)
    merged = ensure_time_env_schema(merged, sql_template=strategy.get('sql_template') or '')
    return filter_env_schema_by_presets(merged, strategy)
