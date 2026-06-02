"""process_pipeline：按块模板顺序编译 process_data(df)。"""
from __future__ import annotations

import re
import uuid
from typing import Any

from studio.flow.flow_compiler import FILTER_RULES_FUNC, PROCESS_FUNC, RANDOM_SAMPLE_FUNC, _repr_value, _sanitize_func_name

# 旧 python_presets → 默认 pipeline 步骤（可多次插入 preset_observe）
_DEFAULT_PIPELINE_BY_PRESETS: dict[tuple[str, ...], list[dict[str, Any]]] = {
    ('observe', 'filter', 'sampling'): [
        {
            'template_id': 'preset_observe',
            'params': {
                'stats_label': 'SQL输出类别统计',
                'df_label': 'SQL输出DataFrame',
                'show_stats': 'yes',
                'show_df': 'yes',
            },
        },
        {'template_id': 'preset_apply_filter_rules', 'params': {}},
        {
            'template_id': 'preset_observe',
            'params': {
                'stats_label': '过滤之后的类别统计',
                'df_label': '过滤之后的DataFrame',
                'show_stats': 'yes',
                'show_df': 'yes',
            },
        },
        {'template_id': 'preset_random_sample', 'params': {}},
        {
            'template_id': 'preset_observe',
            'params': {
                'stats_label': '最终输出的类别统计',
                'df_label': '最终输出的DataFrame',
                'show_stats': 'yes',
                'show_df': 'yes',
            },
        },
    ],
    ('observe', 'filter'): [
        {
            'template_id': 'preset_observe',
            'params': {'stats_label': 'SQL输出类别统计', 'df_label': 'SQL输出DataFrame', 'show_stats': 'yes', 'show_df': 'yes'},
        },
        {'template_id': 'preset_apply_filter_rules', 'params': {}},
        {
            'template_id': 'preset_observe',
            'params': {'stats_label': '过滤后类别统计', 'df_label': '过滤后DataFrame', 'show_stats': 'yes', 'show_df': 'yes'},
        },
    ],
    ('filter', 'sampling'): [
        {'template_id': 'preset_apply_filter_rules', 'params': {}},
        {'template_id': 'preset_random_sample', 'params': {}},
    ],
    ('observe',): [
        {
            'template_id': 'preset_observe',
            'params': {'stats_label': '类别统计', 'df_label': 'DataFrame', 'show_stats': 'yes', 'show_df': 'yes'},
        },
    ],
    ('filter',): [
        {'template_id': 'preset_apply_filter_rules', 'params': {}},
    ],
    ('sampling',): [
        {'template_id': 'preset_random_sample', 'params': {}},
    ],
}

_ALIAS_TEMPLATE_IDS = {
    'random_sample': 'preset_random_sample',
}


def _new_step_id() -> str:
    return 'ps' + uuid.uuid4().hex[:10]


def normalize_pipeline_step(step: dict | None, templates: dict | None = None) -> dict[str, Any]:
    step = dict(step or {})
    tpl_id = str(step.get('template_id') or '').strip()
    tpl_id = _ALIAS_TEMPLATE_IDS.get(tpl_id, tpl_id)
    step['template_id'] = tpl_id
    step.setdefault('id', _new_step_id())
    step.setdefault('params', {})
    if not isinstance(step['params'], dict):
        step['params'] = {}
    return step


def normalize_process_pipeline(pipeline: list | None, templates: dict | None = None) -> list[dict[str, Any]]:
    return [normalize_pipeline_step(s, templates) for s in (pipeline or []) if isinstance(s, dict)]


def default_pipeline_from_python_presets(python_presets: list[str] | None) -> list[dict[str, Any]]:
    key = tuple(sorted(set(python_presets or [])))
    spec = _DEFAULT_PIPELINE_BY_PRESETS.get(key)
    if not spec:
        steps = []
        order = ['observe', 'filter', 'sampling']
        for pid in order:
            if pid in (python_presets or []):
                if pid == 'observe':
                    steps.append({
                        'template_id': 'preset_observe',
                        'params': {'stats_label': '类别统计', 'df_label': 'DataFrame', 'show_stats': 'yes', 'show_df': 'yes'},
                    })
                elif pid == 'filter':
                    steps.append({'template_id': 'preset_apply_filter_rules', 'params': {}})
                elif pid == 'sampling':
                    steps.append({'template_id': 'preset_random_sample', 'params': {}})
        spec = steps
    out = []
    for item in spec:
        out.append(normalize_pipeline_step({'template_id': item['template_id'], 'params': dict(item.get('params') or {})}))
    return out


def ensure_process_pipeline(strategy: dict | None, templates: dict | None = None) -> list[dict[str, Any]]:
    """补齐 process_pipeline；无则从 python_presets 或手写 process_data 迁移。"""
    strategy = strategy or {}
    existing = strategy.get('process_pipeline')
    if isinstance(existing, list) and existing:
        return normalize_process_pipeline(existing, templates)

    presets = strategy.get('python_presets')
    if isinstance(presets, list) and presets:
        return default_pipeline_from_python_presets(presets)

    inferred = _infer_pipeline_from_process_code(strategy.get('python_code') or '')
    if inferred:
        return normalize_process_pipeline(inferred, templates)
    return []


def _infer_pipeline_from_process_code(code: str) -> list[dict[str, Any]]:
    """从既有 process_data 粗粒度推断 pipeline（便于迁移）。"""
    if not code or f'def {PROCESS_FUNC}' not in code:
        return []
    steps: list[dict[str, Any]] = []
    if 'count_category_boxes' in code and 'view' in code:
        for label_m in re.finditer(r'view\s*\(\s*count_category_boxes\s*\(\s*df\s*\)\s*,\s*([^)]+)\)', code):
            steps.append({
                'template_id': 'preset_observe',
                'params': {
                    'stats_label': _parse_py_string(label_m.group(1)),
                    'df_label': 'DataFrame',
                    'show_stats': 'yes',
                    'show_df': 'no',
                },
            })
        for label_m in re.finditer(r'view\s*\(\s*df\s*,\s*([^)]+)\)', code):
            steps.append({
                'template_id': 'preset_observe',
                'params': {
                    'stats_label': '类别统计',
                    'df_label': _parse_py_string(label_m.group(1)),
                    'show_stats': 'no',
                    'show_df': 'yes',
                },
            })
    if FILTER_RULES_FUNC + '(df)' in code.replace(' ', ''):
        steps.append({'template_id': 'preset_apply_filter_rules', 'params': {}})
    if RANDOM_SAMPLE_FUNC in code:
        steps.append({'template_id': 'preset_random_sample', 'params': {}})
    return steps


def _parse_py_string(expr: str) -> str:
    expr = (expr or '').strip()
    if (expr.startswith('"') and expr.endswith('"')) or (expr.startswith("'") and expr.endswith("'")):
        return expr[1:-1]
    return expr


def _format_param_value(key: str, value: Any, *, as_repr: bool = False) -> str:
    if as_repr or key.endswith('_label') or key.endswith('_title'):
        return repr(str(value if value is not None else ''))
    if isinstance(value, bool):
        return 'True' if value else 'False'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, (list, tuple, dict)):
        return repr(value)
    return repr(str(value if value is not None else ''))


def _substitute_line(line: str, params: dict) -> str | None:
    """渲染 process_lines 一行；支持 if {flag}: body。"""
    raw = (line or '').strip()
    if not raw:
        return None
    m = re.match(r'^if\s+\{(\w+)\}\s*:\s*(.+)$', raw)
    if m:
        flag = m.group(1)
        val = params.get(flag, 'yes')
        truthy = val not in (False, 'no', 'false', '0', 0, None, '')
        if not truthy:
            return None
        raw = m.group(2)

    def repl(match: re.Match) -> str:
        key = match.group(1)
        as_repr = match.group(2) == '|r'
        if key not in params:
            return match.group(0)
        return _format_param_value(key, params[key], as_repr=bool(as_repr))

    return re.sub(r'\{(\w+)(\|r)?\}', repl, raw)


def _compile_template_filter_step(
    step: dict,
    tpl: dict,
    tpl_defs: dict,
    tpl_order: list,
    errors: list,
) -> list[str]:
    """块模板 python_code(def filter) → 内联 helper 调用。"""
    sid = step.get('id', '?')
    tpl_id = step['template_id']
    p = step.get('params') or {}
    code = tpl.get('python_code', '')
    if code == '__CUSTOM__':
        code = p.get('code', 'def filter(df, params):\n    return df')
    m = re.search(r'def\s+(\w+)\s*\(', code)
    if not m:
        errors.append(f'[{sid}] 模板无效: {tpl_id}')
        return [f'# invalid template {tpl_id}']
    fn_key = f'{tpl_id}:{sid}'
    fn = f'_tpl_{_sanitize_func_name(tpl_id)}_{_sanitize_func_name(str(sid))}'
    if fn_key not in tpl_defs:
        tpl_defs[fn_key] = code.replace(f'def {m.group(1)}', f'def {fn}', 1)
        tpl_order.append(fn_key)
    return [f'# [{sid}] {tpl.get("name", tpl_id)}', f'df = {fn}(df, {_repr_value(p)})']


def _compile_pipeline_step(
    step: dict,
    templates: dict,
    tpl_defs: dict,
    tpl_order: list,
    errors: list,
) -> list[str]:
    step = normalize_pipeline_step(step, templates)
    sid = step.get('id', '?')
    tpl_id = step['template_id']
    p = step.get('params') or {}
    tpl = templates.get(tpl_id) or {}

    lines = tpl.get('process_lines')
    if lines:
        out = [f'# [{sid}] {tpl.get("name", tpl_id)}']
        for line in lines:
            rendered = _substitute_line(line, p)
            if rendered:
                out.append(rendered)
        return out

    if tpl.get('python_code'):
        return _compile_template_filter_step(step, tpl, tpl_defs, tpl_order, errors)

    errors.append(f'[{sid}] 模板 {tpl_id} 未定义 process_lines 或 python_code')
    return [f'# missing pipeline spec for {tpl_id}']


def compile_process_pipeline(pipeline: list | None, templates: dict | None = None) -> dict[str, Any]:
    """将 process_pipeline 编译为 process_data 源码。"""
    templates = templates or {}
    pipeline = normalize_process_pipeline(pipeline, templates)
    errors: list[str] = []
    tpl_defs: dict[str, str] = {}
    tpl_order: list[str] = []
    body: list[str] = []

    for step in pipeline:
        body.extend(_compile_pipeline_step(step, templates, tpl_defs, tpl_order, errors))

    body.append('return df')
    process_body = '\n'.join(
        ('    ' + ln if ln.strip() else ln) for ln in body
    )
    helpers = '\n\n'.join(tpl_defs[k] for k in tpl_order)
    if helpers:
        code = f'{helpers}\n\n\ndef {PROCESS_FUNC}(df):\n{process_body}\n'
    else:
        code = f'def {PROCESS_FUNC}(df):\n{process_body}\n'

    return {
        'python_code': code,
        'valid': len(errors) == 0,
        'errors': errors,
        'template_helpers': tpl_order,
    }


def preset_groups_from_pipeline(pipeline: list | None, templates: dict | None = None) -> list[str]:
    """pipeline 涉及的预设包 id（去重、保持顺序）。"""
    templates = templates or {}
    seen: list[str] = []
    for step in normalize_process_pipeline(pipeline, templates):
        tpl = templates.get(step['template_id']) or {}
        gid = tpl.get('preset_group')
        if gid and gid not in seen:
            seen.append(str(gid))
    return seen


def inject_functions_from_pipeline(pipeline: list | None, templates: dict | None = None) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()
    for step in normalize_process_pipeline(pipeline, templates):
        tpl = templates.get(step['template_id']) or {}
        for fn in tpl.get('inject_functions') or []:
            if fn not in seen:
                seen.add(fn)
                names.append(str(fn))
    return names


def is_pipeline_eligible_template(tpl: dict | None) -> bool:
    if not tpl:
        return False
    if tpl.get('pipeline'):
        return True
    if tpl.get('process_lines'):
        return True
    if tpl.get('python_code') and tpl.get('python_code') != '__CUSTOM__':
        return True
    return False


def _normalize_py_source(code: str) -> str:
    return '\n'.join(ln.rstrip() for ln in (code or '').strip().splitlines())


def python_code_differs_from_pipeline(strategy: dict | None, templates: dict | None = None) -> bool:
    """手写 process_data 是否与当前 process_pipeline 编译结果不一致。"""
    strategy = strategy or {}
    code = (strategy.get('python_code') or '').strip()
    if not code:
        return False
    pipeline = ensure_process_pipeline(strategy, templates)
    if not pipeline:
        return True
    compiled = compile_process_pipeline(pipeline, templates)
    if not compiled.get('valid'):
        return True
    return _normalize_py_source(code) != _normalize_py_source(compiled.get('python_code') or '')


def resolve_python_code_manual(strategy: dict | None, templates: dict | None = None) -> bool:
    """
    是否保留下方手写 python_code（不被调用链覆盖）。
    显式 python_code_manual 优先；否则当代码与 pipeline 编译结果不一致时视为手写。
    """
    strategy = strategy or {}
    if strategy.get('python_code_manual'):
        return True
    if strategy.get('python_code_manual') is False:
        return False
    return python_code_differs_from_pipeline(strategy, templates)


def list_pipeline_templates(templates: dict | None = None) -> list[dict[str, Any]]:
    out = []
    for tpl in (templates or {}).values():
        if is_pipeline_eligible_template(tpl):
            out.append({
                'id': tpl.get('id'),
                'name': tpl.get('name', tpl.get('id')),
                'description': tpl.get('description', ''),
                'preset_group': tpl.get('preset_group'),
                'category': tpl.get('category', '块模板'),
                'params_schema': tpl.get('params_schema') or [],
            })
    return sorted(out, key=lambda x: (x.get('category') or '', x.get('name') or ''))
