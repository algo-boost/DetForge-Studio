"""Kestra Flow inputs → IISP params_schema / 执行 inputs 规范化。"""
from __future__ import annotations

import json
from typing import Any


def parse_kestra_inputs(flow: dict) -> dict[str, dict]:
    """将 Kestra Flow YAML 的 inputs 转为 WorkflowParamsForm 可用的 params_schema。"""
    schema: dict[str, dict] = {}
    for item in flow.get('inputs') or []:
        if not isinstance(item, dict):
            continue
        iid = str(item.get('id') or '').strip()
        if not iid:
            continue
        ktype = str(item.get('type') or 'STRING').upper()
        has_default = 'defaults' in item or 'default' in item
        required = item.get('required')
        if required is None:
            required = not has_default

        field: dict[str, Any] = {
            'label': str(item.get('description') or iid.replace('_', ' ')),
            'required': bool(required),
        }

        default = item.get('defaults') if 'defaults' in item else item.get('default')
        # 语义字段（策略 / 模型）优先按业务控件渲染，不受声明的标量类型影响
        if iid == 'strategy_id':
            field['type'] = 'strategy'
        elif iid in ('model_id', 'train_id'):
            field['type'] = 'model'
        elif ktype == 'JSON':
            if isinstance(default, str):
                try:
                    default = json.loads(default)
                except (TypeError, ValueError):
                    pass
            if iid == 'time_window' or (isinstance(default, dict) and 'preset' in default):
                field['type'] = 'time_window'
            else:
                field['type'] = 'json'
        elif ktype in ('INT', 'INTEGER'):
            field['type'] = 'integer'
        elif ktype in ('FLOAT', 'DOUBLE'):
            field['type'] = 'number'
        elif ktype == 'BOOLEAN':
            field['type'] = 'boolean'
        else:
            field['type'] = 'string'

        if default is not None:
            field['default'] = default
        schema[iid] = field
    return schema


def apply_input_defaults(inputs: dict | None, params_schema: dict) -> dict:
    """合并 schema 默认值与用户提交值。"""
    out: dict = {}
    for key, spec in (params_schema or {}).items():
        if spec.get('default') is not None:
            out[key] = spec['default']
    if inputs:
        for key, val in inputs.items():
            if val is None or val == '':
                continue
            out[key] = val
    return out


def normalize_execution_inputs(inputs: dict, params_schema: dict | None = None) -> dict:
    """规范化后提交给 Kestra executions API。"""
    schema = params_schema or {}
    out: dict = {}
    for key, val in (inputs or {}).items():
        if val is None or val == '':
            continue
        spec = schema.get(key) or {}
        ftype = spec.get('type') or 'string'
        if ftype == 'json' and isinstance(val, str):
            try:
                val = json.loads(val)
            except (TypeError, ValueError):
                pass
        if ftype == 'integer' and val != '':
            val = int(val)
        if ftype == 'number' and val != '':
            val = float(val)
        out[key] = val
    return out


def extract_kestra_task_outline(flow: dict) -> list[dict]:
    """从 tasks 树提取步骤 id 概览（供 Flow 卡片展示）。"""
    from orchestration.kestra_graph import extract_kestra_flow_graph

    graph = extract_kestra_flow_graph(flow)
    return [
        {'id': n['id'], 'tool': n.get('tool_id') or n.get('kind')}
        for n in graph.get('nodes') or []
        if n.get('node_kind') != 'log'
    ]
