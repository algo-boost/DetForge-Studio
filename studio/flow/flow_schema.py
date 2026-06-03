"""
Flow IR v2 & Strategy v2 规范

设计原则（对齐 Coze / n8n / Temporal 子集）：
- 策略 = SQL + Flow 工作流 + 采样；Python 仅为编译产物或 code 模式手写
- 节点两类：action（叶子）| container（if / loop）
- 容器通过命名分支嵌套：if.then / if.else / loop.body
- 无限嵌套，编译器递归 lowering 为 process_data(df)
"""

FLOW_IR_VERSION = 2
STRATEGY_SCHEMA_VERSION = 2

CONTAINER_TYPES = frozenset({'control.if', 'control.loop'})
CONTAINER_BRANCHES = {
    'control.if': ('then', 'else'),
    'control.loop': ('body',),
}


def empty_flow():
    return {'version': FLOW_IR_VERSION, 'nodes': []}


def _ensure_container(node):
    t = node.get('type')
    if t == 'control.if':
        node.setdefault('then', [])
        node.setdefault('else', [])
    elif t == 'control.loop':
        node.setdefault('body', [])
        node['params'] = node.get('params') or {}
        if node['params'].get('loop_mode') == 'rules':
            node['params'].setdefault('rules', [])


def prepare_node(node):
    """规范化节点结构（非迁移，仅补齐缺省字段）。"""
    if not node or 'type' not in node:
        return node
    node.setdefault('id', '')
    node.setdefault('params', {})
    if node['type'] in CONTAINER_TYPES:
        _ensure_container(node)
        for branch in CONTAINER_BRANCHES[node['type']]:
            node[branch] = [prepare_node(c) for c in (node.get(branch) or [])]
    return node


def prepare_flow(flow):
    flow = flow or {}
    nodes = [prepare_node(dict(n)) for n in (flow.get('nodes') or [])]
    return {'version': FLOW_IR_VERSION, 'nodes': nodes}


REMOVE_EMPTY_NODE_TYPE = 'builtin.remove_empty_ext_rows'
FILTER_NODE_TYPE = 'builtin.filter_df_by_ext'


def _is_rules_loop(node):
    if not node or node.get('type') != 'control.loop':
        return False
    if (node.get('params') or {}).get('loop_mode', 'rules') != 'rules':
        return False
    body = node.get('body') or []
    rules = (node.get('params') or {}).get('rules')
    return (
        any(n.get('type') == FILTER_NODE_TYPE for n in body)
        or any(n.get('type') == REMOVE_EMPTY_NODE_TYPE for n in body)
        or (isinstance(rules, list) and len(rules) > 0)
    )


def flow_has_remove_empty_rows(flow):
    flow = prepare_flow(flow)

    def walk(node):
        if not node:
            return False
        if node.get('type') == REMOVE_EMPTY_NODE_TYPE:
            return True
        for branch in CONTAINER_BRANCHES.get(node.get('type'), ()):
            for child in node.get(branch) or []:
                if walk(child):
                    return True
        return False

    return any(walk(n) for n in flow.get('nodes') or [])


def sync_remove_empty_in_flow(flow, enabled):
    """与前端 flowTree.syncRulesLoopRemoveEmpty 一致。"""
    flow = prepare_flow(flow or {})
    loop = next((n for n in flow['nodes'] if _is_rules_loop(n)), None)
    if not loop:
        return flow
    body = [dict(n) for n in (loop.get('body') or []) if n.get('type') != REMOVE_EMPTY_NODE_TYPE]
    if enabled:
        if not any(n.get('type') == FILTER_NODE_TYPE for n in body):
            body.insert(0, {
                'id': 'f_filter',
                'type': FILTER_NODE_TYPE,
                'params': {'bind_loop_rule': 'loop_rule'},
            })
        body.append({'id': 'f_remove_empty', 'type': REMOVE_EMPTY_NODE_TYPE, 'params': {}})
    loop['body'] = body
    return flow


def validate_node(node, path='root', errors=None):
    errors = errors if errors is not None else []
    if not node:
        errors.append(f'{path}: 空节点')
        return errors
    nid = node.get('id') or '?'
    t = node.get('type', '')
    label = f'{path}[{nid}]'
    if not t:
        errors.append(f'{label}: 缺少 type')
        return errors
    if t in CONTAINER_TYPES:
        branches = CONTAINER_BRANCHES[t]
        for b in branches:
            for i, child in enumerate(node.get(b) or []):
                validate_node(child, f'{label}.{b}[{i}]', errors)
        if t == 'control.loop':
            mode = (node.get('params') or {}).get('loop_mode', 'rules')
            if mode not in ('count', 'while_rows', 'rules'):
                errors.append(f'{label}: 未知 loop_mode: {mode}')
    return errors


def validate_flow(flow):
    errors = []
    flow = flow or {}
    if flow.get('version') not in (None, FLOW_IR_VERSION, 2):
        errors.append(f'不支持的 flow.version: {flow.get("version")}')
    for i, node in enumerate(flow.get('nodes') or []):
        validate_node(node, f'nodes[{i}]', errors)
    return errors


VALID_DATA_SOURCES = frozenset({'detail', 'predict_result'})


def normalize_strategy_data_source(data_source, sql_template=''):
    """策略保存/加载时统一数据源：显式字段优先，否则按 SQL 推断。"""
    raw = str(data_source or '').strip().lower()
    if raw in VALID_DATA_SOURCES:
        return raw
    sql = str(sql_template or '').lower()
    if 'predict_result' in sql:
        return 'predict_result'
    return 'detail'


def prepare_strategy(data):
    """保存前规范化 Strategy v2。"""
    from studio.flow.process_pipeline import (
        compile_process_pipeline,
        ensure_process_pipeline,
        preset_groups_from_pipeline,
        resolve_python_code_manual,
    )
    from studio.query.strategy_env_schema import sync_env_schema_with_capabilities

    s = dict(data or {})
    s['schema_version'] = STRATEGY_SCHEMA_VERSION
    s['data_source'] = normalize_strategy_data_source(s.get('data_source'), s.get('sql_template'))
    job_raw = s.get('default_predict_job_id')
    if s['data_source'] == 'predict_result' and job_raw not in (None, ''):
        try:
            jid = int(job_raw)
            if jid > 0:
                s['default_predict_job_id'] = jid
            else:
                s.pop('default_predict_job_id', None)
        except (TypeError, ValueError):
            s.pop('default_predict_job_id', None)
    else:
        s.pop('default_predict_job_id', None)
    s.setdefault('filter_mode', 'flow' if s.get('flow', {}).get('nodes') else 'code')
    if s.get('flow'):
        if 'remove_empty_rows' in s:
            s['flow'] = sync_remove_empty_in_flow(s['flow'], bool(s['remove_empty_rows']))
        else:
            s['flow'] = prepare_flow(s['flow'])
            s['remove_empty_rows'] = flow_has_remove_empty_rows(s['flow'])
    elif 'remove_empty_rows' not in s:
        s['remove_empty_rows'] = True
    cleaned_schema = []
    for row in s.get('env_schema') or []:
        if not isinstance(row, dict):
            continue
        row = dict(row)
        row.pop('_optionsText', None)
        cleaned_schema.append(row)
    templates = None
    try:
        from studio.query.strategy_loader import get_all_templates
        templates = get_all_templates()
    except Exception:
        pass
    s['env_schema'] = sync_env_schema_with_capabilities(s, templates)
    pipeline = ensure_process_pipeline(s, templates)
    s['process_pipeline'] = pipeline
    manual = resolve_python_code_manual(s, templates)
    s['python_code_manual'] = manual
    if pipeline and not manual:
        compiled = compile_process_pipeline(pipeline, templates)
        if compiled.get('valid') and compiled.get('python_code'):
            s['python_code'] = compiled['python_code']
    s['python_presets'] = preset_groups_from_pipeline(pipeline, templates) if pipeline else (s.get('python_presets') or [])
    # v2 不再使用 pipeline
    s.pop('pipeline', None)
    s.pop('type', None)
    ui_mode = s.get('query_ui_mode')
    allowed_hide = {
        'data_source', 'predict_job', 'strategy_params', 'filter_rules',
        'preview_button', 'preview_stats', 'compact_hint', 'strategy_tools',
    }
    if ui_mode not in ('full', 'compact'):
        s.pop('query_ui_mode', None)
        s.pop('query_compact_hide', None)
    else:
        s['query_ui_mode'] = ui_mode
        hide = s.get('query_compact_hide')
        if ui_mode != 'compact':
            s.pop('query_compact_hide', None)
        elif isinstance(hide, dict):
            s['query_compact_hide'] = {
                k: bool(hide[k]) for k in allowed_hide if k in hide
            }
        elif hide is not None:
            s.pop('query_compact_hide', None)
    return s


def strategy_descriptor(strategy):
    """列表展示用简短描述。"""
    mode = strategy.get('filter_mode', 'code')
    flow = strategy.get('flow') or {}
    n = len(flow.get('nodes') or [])
    if mode in ('flow', 'split') and n:
        return f'工作流 · {n} 步'
    if mode == 'code':
        return 'SQL + 代码'
    return 'SQL 查询'
