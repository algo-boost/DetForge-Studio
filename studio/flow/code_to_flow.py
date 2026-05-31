"""将 process_data(df) Python 代码解析为 Flow IR v2。"""
import ast
import re
import uuid

from studio.flow.flow_schema import FLOW_IR_VERSION, prepare_flow

FILTER_RE = re.compile(
    r"filter_df_by_ext\s*\(\s*(?:filter_df|df)\s*,\s*categories\s*=\s*(\[[^\]]*\])"
    r"(?:\s*,\s*confidence_range\s*=\s*\(([^)]+)\))?"
    r"(?:\s*,\s*random_drop_ratio\s*=\s*([^)]+))?"
    r"\s*\)",
    re.MULTILINE,
)
SAMPLE_IF_RE = re.compile(
    r"if\s+len\s*\(\s*filter_df\s*\)\s*>\s*(\d+)\s*:.*?\.sample\s*\(\s*n\s*=\s*(\d+)"
    r"(?:\s*,\s*random_state\s*=\s*(\d+))?",
    re.DOTALL,
)
JOIN_RE = re.compile(
    r"df\s*\[\s*df\s*\[\s*['\"]origin_object_key['\"]\s*\]\s*\.isin\s*\(\s*filter_df\s*\[\s*['\"]origin_object_key['\"]\s*\]\s*\)\s*\]"
)


def _uid(prefix='n'):
    return prefix + uuid.uuid4().hex[:8]


def _parse_float_pair(s):
    if not s:
        return [0.0, 1.0]
    parts = [p.strip() for p in s.split(',')]
    return [float(parts[0]), float(parts[1]) if len(parts) > 1 else 1.0]


def _parse_categories(raw):
    return ast.literal_eval(raw)


def _parse_ratio(raw):
    if raw is None:
        return 1.0
    return float(raw.strip())


def _extract_process_body(code):
    code = (code or '').strip()
    m = re.search(r'def\s+process_data\s*\(\s*df\s*\)\s*:\s*(.*)', code, re.DOTALL)
    if not m:
        raise ValueError('未找到 def process_data(df):')
    return m.group(1)


def _tpl_node(code, nid=None):
    return {
        'id': nid or _uid('py'),
        'type': 'template.python_code',
        'template_id': 'python_code',
        'params': {'code': code.strip()},
    }


def _strip_comments(text):
    lines = []
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith('#'):
            continue
        lines.append(ln)
    return '\n'.join(lines)


def _first_filter_pos(body):
    m = re.search(
        r'filter_df\s*=\s*remove_empty_ext_rows\s*\(\s*filter_df_by_ext\s*\(\s*df\s*,',
        body,
    )
    return m.start() if m else None


def _parse_pre_loop_block(body, nodes):
    """循环筛选前的自定义逻辑（如 product_no 统计 + view）。"""
    pos = _first_filter_pos(body)
    if pos is None:
        return body
    pre = body[:pos].strip()
    if not pre:
        nodes.append(_tpl_node(
            '_ORIG_DF = None\n\n'
            'def filter(df, params):\n'
            '    global _ORIG_DF\n'
            '    _ORIG_DF = df.copy()\n'
            '    return df',
            _uid('snap'),
        ))
        return body[pos:]
    snippet = (
        '_ORIG_DF = None\n\n'
        'def filter(df, params):\n'
        '    global _ORIG_DF\n'
        '    _ORIG_DF = df.copy()\n'
        + '\n'.join('    ' + ln.strip() for ln in pre.splitlines() if ln.strip())
        + '\n    return df'
    )
    nodes.append(_tpl_node(snippet, _uid('pre')))
    return body[pos:]


def code_to_flow(python_code):
    """解析 process_data 代码 → Flow IR v2 dict。"""
    body = _strip_comments(_extract_process_body(python_code))
    nodes = []

    pos = _first_filter_pos(body)
    if pos is None:
        raise ValueError('代码中未识别到 filter_df_by_ext 筛选链')
    body = _parse_pre_loop_block(body, nodes)

    rules = []
    for m in FILTER_RE.finditer(body):
        cats = _parse_categories(m.group(1))
        cr = _parse_float_pair(m.group(2))
        ratio = _parse_ratio(m.group(3))
        rules.append({
            'categories': cats,
            'confidence_range': cr,
            'random_drop_ratio': ratio,
        })

    if not rules:
        raise ValueError('未能解析筛选规则')

    loop_id = _uid('loop')
    nodes.append({
        'id': loop_id,
        'type': 'control.loop',
        'params': {'loop_mode': 'rules', 'rules': rules},
        'body': [
            {
                'id': _uid('f'),
                'type': 'builtin.filter_df_by_ext',
                'params': {'bind_loop_rule': 'loop_rule'},
            },
            {
                'id': _uid('r'),
                'type': 'builtin.remove_empty_ext_rows',
                'params': {},
            },
        ],
    })

    sm = SAMPLE_IF_RE.search(body)
    if sm:
        max_rows = int(sm.group(2))
        seed = int(sm.group(3) or 42)
        nodes.append({
            'id': _uid('s'),
            'type': 'template.random_sample',
            'template_id': 'random_sample',
            'params': {'max_rows': max_rows, 'random_seed': seed},
        })

    if re.search(r'\bview\s*\(\s*filter_df\s*\)', body):
        nodes.append({
            'id': _uid('v'),
            'type': 'builtin.view',
            'params': {'label': 'filter_df'},
        })

    if re.search(r'count_category_boxes\s*\(\s*df\s*\)', body):
        obs_lines = []
        if re.search(r'count_category_boxes\s*\(\s*df\s*\)', body):
            obs_lines.append('    view(count_category_boxes(_ORIG_DF))')
        if re.search(r'count_category_boxes\s*\(\s*filter_df\s*\)', body):
            obs_lines.append('    view(count_category_boxes(df))')
        if re.search(r'print\s*\(\s*filter_df\.shape', body):
            obs_lines.append('    print(df.shape, _ORIG_DF.shape)')
        if obs_lines:
            nodes.append(_tpl_node(
                'def filter(df, params):\n' + '\n'.join(obs_lines) + '\n    return df',
                _uid('obs'),
            ))

    if JOIN_RE.search(body):
        nodes.append(_tpl_node(
            "def filter(df, params):\n"
            "    res = _ORIG_DF[_ORIG_DF['origin_object_key'].isin(df['origin_object_key'])]\n"
            "    view(res)\n"
            "    return res",
            _uid('join'),
        ))
    elif re.search(r'return\s+filter_df\b', body):
        pass  # 编译后 df 即 filter_df
    elif re.search(r'return\s+res_df\b', body) and not JOIN_RE.search(body):
        pass

    return prepare_flow({'version': FLOW_IR_VERSION, 'nodes': nodes})


def strategy_from_code(strategy, python_code=None):
    """Strategy dict 注入 flow + filter_mode。"""
    code = python_code or strategy.get('python_code', '')
    flow = code_to_flow(code)
    out = dict(strategy)
    out['schema_version'] = 2
    out['filter_mode'] = 'flow'
    out['flow'] = flow
    out.pop('pipeline', None)
    out.pop('type', None)
    return out
