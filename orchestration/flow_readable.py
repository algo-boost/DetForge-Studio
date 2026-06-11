"""Flow 节点可读化：YAML 中文注释 + 表单化入参/出参（非 YAML 原文）。"""
from __future__ import annotations

import json
import re
from typing import Any

from orchestration.param_labels import (
    output_description,
    output_title,
    param_description,
    param_title,
)

_STEP_HEADER_RE = re.compile(
    r'#\s*【步骤\s+(\w+)】工具\s+([\w-]+)\s*[—\-]\s*(.+)$',
)
_STEP_SHORT_RE = re.compile(r'#\s*【步骤\s+(\w+)】\s*(.*)$')
_BRANCH_HEADER_RE = re.compile(r'#\s*【分支\s+(\w+)】\s*(.*)$')
_STEP_ID_RE = re.compile(r'^\s*-\s*id:\s*(\S+)')
_INPUTS_LINE_RE = re.compile(r'#\s*入参[：:]\s*(.+)$')
_OUTPUTS_LINE_RE = re.compile(r'#\s*出参[：:]\s*(.+)$')
_UPSTREAM_LINE_RE = re.compile(r'#\s*上游包[：:]\s*(.+)$')
_FLOW_SUMMARY_RE = re.compile(r'#\s*流程一句话[：:]\s*(.+)$')
_FLOW_DATA_RE = re.compile(r'#\s*数据接力[：:]\s*(.+)$')

_PARAM_KV_RE = re.compile(r'"(\w+)"\s*:\s*([^,\n}]+)')
_INPUTS_REF_RE = re.compile(r'\binputs\.(\w+)\b')
_OUTPUTS_REF_RE = re.compile(
    r'fromJson\(outputs\.(\w+)\.body\)(?:\.outputs(?:\.(\w+))?)?',
)
_OUTPUT_KEYS_RE = re.compile(r'([\w_]+)(?:\s*、\s*|\s*,\s*)?')


def parse_yaml_flow_header(yaml_text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (yaml_text or '').splitlines():
        s = line.strip()
        m = _FLOW_SUMMARY_RE.match(s)
        if m:
            out['summary'] = m.group(1).strip()
            continue
        m = _FLOW_DATA_RE.match(s)
        if m:
            out['data_flow'] = m.group(1).strip()
    return out


def parse_yaml_step_comments(yaml_text: str) -> dict[str, dict[str, str]]:
    """解析每个 `- id:` 前的中文注释块。"""
    rows: dict[str, dict[str, str]] = {}
    pending: list[str] = []

    for line in (yaml_text or '').splitlines():
        stripped = line.strip()
        if stripped.startswith('#'):
            pending.append(stripped.lstrip('#').strip())
            continue

        m = _STEP_ID_RE.match(line)
        if not m:
            continue

        step_id = m.group(1)
        meta: dict[str, str] = {'comments': '\n'.join(pending)}
        for comment in pending:
            bm = _BRANCH_HEADER_RE.match(f'# {comment}')
            if bm:
                meta['step_id'] = bm.group(1)
                meta['node_kind'] = 'branch'
                rest = bm.group(2).strip()
                if rest:
                    meta['title'] = rest
                continue
            hm = _STEP_HEADER_RE.match(f'# {comment}')
            if hm:
                meta['step_id'] = hm.group(1)
                meta['tool_id'] = hm.group(2)
                meta['title'] = hm.group(3).strip()
                continue
            sm = _STEP_SHORT_RE.match(f'# {comment}')
            if sm:
                meta['step_id'] = sm.group(1)
                rest = sm.group(2).strip()
                if not rest:
                    continue
                if '←' in rest or '->' in rest:
                    meta['inputs_line'] = rest.replace('->', '←')
                elif '→' in rest:
                    meta['outputs_line'] = rest
                else:
                    meta['title'] = rest
                continue
            im = _INPUTS_LINE_RE.match(f'# {comment}')
            if im:
                meta['inputs_line'] = im.group(1).strip()
            om = _OUTPUTS_LINE_RE.match(f'# {comment}')
            if om:
                meta['outputs_line'] = om.group(1).strip()
            um = _UPSTREAM_LINE_RE.match(f'# {comment}')
            if um:
                meta['upstream_line'] = um.group(1).strip()
        rows[step_id] = meta
        pending = []

    return rows


def humanize_pebble_expr(expr: str, *, flow_inputs: set[str] | None = None) -> str:
    text = str(expr or '').strip().rstrip(',')
    if not text:
        return '—'
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    if text in ('{}', '[]'):
        return '空'

    m = _INPUTS_REF_RE.search(text)
    if m and text.strip() == f'inputs.{m.group(1)}':
        key = m.group(1)
        title = param_title(key)
        if flow_inputs and key in flow_inputs:
            return f'Flow 入参「{title}」（{key}）'
        return f'Flow 入参「{title}」'

    m = _OUTPUTS_REF_RE.search(text)
    if m:
        step, out_key = m.group(1), m.group(2)
        if out_key:
            return f'上一步「{step}」的 {param_title(out_key)}（{out_key}）'
        return f'上一步「{step}」的完整 outputs'

    if text.startswith('execution.'):
        return 'Kestra 执行上下文'
    return text


def extract_invoke_params(body: str | None) -> dict[str, Any]:
    if not body:
        return {}
    text = str(body)
    params: dict[str, Any] = {}
    block_match = re.search(r'"params"\s*:\s*\{', text)
    if not block_match:
        return params
    start = block_match.end()
    depth = 1
    i = start
    while i < len(text) and depth > 0:
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
        i += 1
    block = text[start:i - 1]
    for m in _PARAM_KV_RE.finditer(block):
        key, raw = m.group(1), m.group(2).strip()
        if key in ('run_id', 'step_id'):
            continue
        params[key] = raw
    return params


def _schema_field_hint(schema: dict | None, key: str) -> str:
    if not isinstance(schema, dict):
        return ''
    props = schema.get('properties') or {}
    spec = props.get(key) if isinstance(props, dict) else None
    if not isinstance(spec, dict):
        return ''
    return str(spec.get('description') or spec.get('title') or '').strip()


def _humanize_source_ref(text: str) -> str:
    raw = str(text or '').strip()
    m = re.match(r'inputs(?:\.(\w+))?', raw)
    if m:
        if m.group(1):
            return f'Flow 入参「{param_title(m.group(1))}」'
        return 'Flow 入参'
    m = re.search(r'(\w+)\.outputs\.(\w+)', raw)
    if m:
        return f'上一步「{m.group(1)}」的 {param_title(m.group(2))}'
    m = re.search(r'(\w+)\.outputs', raw)
    if m:
        return f'上一步「{m.group(1)}」的 outputs'
    return raw


def _parse_inputs_line(line: str) -> dict[str, str]:
    """入参行 → key → 来源说明。"""
    hints: dict[str, str] = {}
    for part in re.split(r'[；;]', line or ''):
        part = part.strip()
        if not part:
            continue
        m = re.match(r'(.+?)\s*←\s*(.+)', part)
        if m:
            keys = re.split(r'[、,]\s*', m.group(1).strip())
            source = _humanize_source_ref(m.group(2).strip())
            for key in keys:
                key = key.strip()
                if key:
                    hints[key] = source
            continue
        m = re.match(r'(\w+)\s+写死(.+)', part)
        if m:
            hints[m.group(1)] = f'固定值（{m.group(2).strip()}）'
    return hints


def _parse_outputs_line(line: str) -> list[dict[str, str]]:
    """出参行 → [{key, used_by, note}]。"""
    if not line:
        return []
    dest = ''
    body = line
    if '→' in line:
        body, dest = [p.strip() for p in line.split('→', 1)]
    keys = re.split(r'[、,]\s*', body)
    rows = []
    for key in keys:
        key = key.strip()
        if not key or key in ('无', '—'):
            continue
        rows.append({
            'key': key,
            'used_by': dest,
            'note': f'传递给 {dest}' if dest else '',
        })
    return rows


_STATUS_LABELS = {
    'done': '成功完成',
    'skipped': '已跳过',
    'failed': '失败',
    'waiting_human': '等待人工',
    'running': '执行中',
}


def humanize_branch_condition(condition: str | None) -> dict[str, Any]:
    text = str(condition or '').strip()
    text = re.sub(r'^\{\{\s*', '', text)
    text = re.sub(r'\s*\}\}$', '', text)

    inputs_form: list[dict[str, Any]] = []
    outputs_form: list[dict[str, Any]] = []
    summary = '按条件决定后续走主链路或备用分支'

    m = re.search(
        r'fromJson\(outputs\.(\w+)\.body\)\.status\s*==\s*[\'"](\w+)[\'"]',
        text,
    )
    if m:
        step, status = m.group(1), m.group(2)
        status_cn = _STATUS_LABELS.get(status, status)
        summary = f'当上一步「{step}」{status_cn}（status={status}）时，进入主链路；否则走空结果分支'
        inputs_form.append({
            'key': 'status',
            'title': '执行状态',
            'description': f'读取步骤「{step}」HTTP 返回体中的 status 字段',
            'value': f'等于 {status}（{status_cn}）',
            'value_raw': text,
        })
        outputs_form.extend([
            {
                'key': 'then',
                'title': '条件成立',
                'description': '进入 then 主链路',
                'value': '批次 → 导出 → 人工卡点 → 导入 → 归档 → 通知',
                'used_by': '主流程',
            },
            {
                'key': 'else',
                'title': '条件不成立',
                'description': '查询无结果、跳过或失败时',
                'value': '记录 empty_result 日志并结束',
                'used_by': '空结果分支',
            },
        ])
    elif text:
        inputs_form.append({
            'key': 'condition',
            'title': '分支条件',
            'description': 'Kestra If 表达式',
            'value': humanize_pebble_expr(text),
            'value_raw': text,
        })

    return {
        'step_title': '条件分支',
        'step_summary': summary,
        'inputs': inputs_form,
        'outputs': outputs_form,
        'branch_condition': text,
        'branch_condition_human': summary,
    }


def build_node_readable(
    node: dict,
    *,
    yaml_meta: dict | None = None,
    flow_inputs: set[str] | None = None,
) -> dict[str, Any]:
    yaml_meta = yaml_meta or {}
    if node.get('node_kind') == 'branch' or node.get('tool_id') == 'branch':
        readable = humanize_branch_condition(node.get('description'))
        if yaml_meta.get('title'):
            readable['step_summary'] = yaml_meta['title']
        if yaml_meta.get('node_kind') == 'branch' and not yaml_meta.get('title'):
            readable['step_title'] = f"条件分支 · {node.get('id') or ''}".strip(' ·')
        return readable

    tool = node.get('tool') or {}
    schema = tool.get('params_schema') or {}
    invoke_raw = extract_invoke_params(node.get('request_body_preview'))
    if not invoke_raw and node.get('params_preview'):
        invoke_raw = dict(node.get('params_preview') or {})

    input_hints = _parse_inputs_line(yaml_meta.get('inputs_line', ''))
    output_defs = _parse_outputs_line(yaml_meta.get('outputs_line', ''))

    inputs_form: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for key, raw_expr in invoke_raw.items():
        seen_keys.add(key)
        hint = input_hints.get(key, '')
        desc = param_description(key, fallback=_schema_field_hint(schema, key))
        if hint and hint not in desc:
            desc = f'{desc}；来源：{hint}' if desc else f'来源：{hint}'
        inputs_form.append({
            'key': key,
            'title': param_title(key),
            'description': desc,
            'value': humanize_pebble_expr(str(raw_expr), flow_inputs=flow_inputs),
            'value_raw': str(raw_expr),
        })

    for key, hint in input_hints.items():
        if key in seen_keys:
            continue
        inputs_form.append({
            'key': key,
            'title': param_title(key),
            'description': param_description(key, fallback=_schema_field_hint(schema, key)),
            'value': hint,
            'value_raw': hint,
        })

    outputs_form: list[dict[str, Any]] = []
    if output_defs:
        for item in output_defs:
            key = item['key']
            outputs_form.append({
                'key': key,
                'title': output_title(key),
                'description': output_description(key, fallback=item.get('note', '')),
                'used_by': item.get('used_by') or '',
            })
    else:
        for key in tool.get('outputs') or []:
            outputs_form.append({
                'key': key,
                'title': output_title(str(key)),
                'description': output_description(str(key)),
                'used_by': '',
            })

    title = yaml_meta.get('title') or tool.get('label') or node.get('tool_id') or node.get('id')
    return {
        'step_title': title,
        'step_summary': yaml_meta.get('title') or tool.get('description') or '',
        'upstream_note': yaml_meta.get('upstream_line') or '',
        'inputs': inputs_form,
        'outputs': outputs_form,
        'yaml_hints': {
            'inputs_line': yaml_meta.get('inputs_line') or '',
            'outputs_line': yaml_meta.get('outputs_line') or '',
        },
    }


def apply_run_io_to_readable(readable: dict, io: dict | None) -> dict:
    """运行态：把实际 outputs 填入表单。"""
    if not io or not isinstance(readable, dict):
        return readable
    outputs = io.get('outputs')
    if not isinstance(outputs, dict):
        return readable

    out_by_key = {str(o.get('key')): o for o in readable.get('outputs') or []}
    for key, val in outputs.items():
        key = str(key)
        if key in out_by_key:
            out_by_key[key]['actual'] = val
            out_by_key[key]['actual_display'] = _format_value(val)
        else:
            readable.setdefault('outputs', []).append({
                'key': key,
                'title': output_title(key),
                'description': output_description(key),
                'actual': val,
                'actual_display': _format_value(val),
            })

    params = (io.get('raw_body') or {}).get('params') if isinstance(io.get('raw_body'), dict) else None
    if isinstance(params, dict):
        in_by_key = {str(i.get('key')): i for i in readable.get('inputs') or []}
        for key, val in params.items():
            key = str(key)
            if key in in_by_key:
                in_by_key[key]['actual'] = val
                in_by_key[key]['actual_display'] = _format_value(val)

    readable['run_status'] = io.get('status')
    return readable


def _format_value(val: Any) -> str:
    if val is None:
        return '—'
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def enrich_graph_readable(
    graph: dict,
    *,
    yaml_text: str | None = None,
    flow_defn: dict | None = None,
) -> dict[str, Any]:
    yaml_text = yaml_text or ''
    step_comments = parse_yaml_step_comments(yaml_text)
    header = parse_yaml_flow_header(yaml_text)

    flow_inputs: set[str] = set()
    for item in (flow_defn or {}).get('inputs') or []:
        if isinstance(item, dict) and item.get('id'):
            flow_inputs.add(str(item['id']))

    nodes = []
    for node in graph.get('nodes') or []:
        copy = dict(node)
        meta = step_comments.get(copy.get('id') or '', {})
        readable = build_node_readable(copy, yaml_meta=meta, flow_inputs=flow_inputs)
        if copy.get('io'):
            readable = apply_run_io_to_readable(readable, copy.get('io'))
        copy['readable'] = readable
        nodes.append(copy)

    result = {**graph, 'nodes': nodes}
    readable_header = dict(header)
    if flow_defn:
        desc = flow_defn.get('description')
        if desc:
            readable_header['description'] = str(desc).strip()
        readable_header['flow_id'] = flow_defn.get('id') or graph.get('flow_id')
    if readable_header:
        result['readable'] = readable_header
    return result
