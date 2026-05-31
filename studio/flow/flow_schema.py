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


def prepare_strategy(data):
    """保存前规范化 Strategy v2。"""
    s = dict(data or {})
    s['schema_version'] = STRATEGY_SCHEMA_VERSION
    s.setdefault('filter_mode', 'flow' if s.get('flow', {}).get('nodes') else 'code')
    if s.get('flow'):
        s['flow'] = prepare_flow(s['flow'])
    # v2 不再使用 pipeline
    s.pop('pipeline', None)
    s.pop('type', None)
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
