"""Flow IR v2 → Python 编译器。"""
import re

from studio.flow.flow_schema import CONTAINER_TYPES, prepare_flow, validate_flow
from studio.flow.flow_registry import is_container_type

OP_MAP = {'gt': '>', 'gte': '>=', 'lt': '<', 'lte': '<=', 'eq': '==', 'neq': '!='}

FILTER_RULES_FUNC = 'apply_filter_rules'
PROCESS_FUNC = 'process_data'
RANDOM_SAMPLE_FUNC = 'apply_random_sample_rows'

_RULES_DEF_RE = re.compile(rf'def\s+{re.escape(FILTER_RULES_FUNC)}\s*\(')
_RULES_CALL_RE = re.compile(rf'\b{re.escape(FILTER_RULES_FUNC)}\s*\(')


def has_filter_rules_definition(code: str) -> bool:
    return bool(_RULES_DEF_RE.search(code or ''))


def references_filter_rules(code: str) -> bool:
    text = code or ''
    if has_filter_rules_definition(text):
        return False
    return bool(_RULES_CALL_RE.search(text))


def references_random_sample(code: str) -> bool:
    text = code or ''
    if re.search(rf'def\s+{re.escape(RANDOM_SAMPLE_FUNC)}\s*\(', text):
        return False
    return bool(re.search(rf'\b{re.escape(RANDOM_SAMPLE_FUNC)}\s*\(', text))


def _repr_value(v):
    if isinstance(v, (list, tuple)):
        return repr(list(v))
    return repr(v)


def _sanitize_func_name(tpl_id):
    return re.sub(r'[^a-zA-Z0-9_]', '_', tpl_id)


def _indent_lines(lines, level):
    pad = '    ' * level
    return [pad + ln if ln.strip() else ln for ln in lines]


def _is_redundant_sample_if(node):
    """if len(df) > N 内仅 random_sample — apply_random_sample_rows 已内置行数判断。"""
    if node.get('type') != 'control.if':
        return False
    p = node.get('params') or {}
    if p.get('condition_type', 'row_count') != 'row_count':
        return False
    if p.get('op', 'gt') != 'gt':
        return False
    if node.get('else'):
        return False
    then_nodes = node.get('then') or []
    if len(then_nodes) != 1:
        return False
    child = then_nodes[0]
    t = child.get('type', '')
    tid = child.get('template_id') or ''
    return t == 'template.random_sample' or tid == 'random_sample'


def _compile_condition(params):
    p = params or {}
    ctype = p.get('condition_type', 'row_count')
    if ctype == 'always':
        return 'True'
    if ctype == 'not_empty':
        return 'len(df) > 0'
    op = OP_MAP.get(p.get('op', 'gt'), '>')
    value = int(p.get('value', 0))
    return f'len(df) {op} {value}'


def _compile_filter(params, in_rules_loop=False):
    p = params or {}
    if p.get('bind_loop_rule') == 'loop_rule' or (in_rules_loop and p.get('bind_loop_rule') != 'manual'):
        return [
            "if _loop_rule.get('confidence_mode') == 'min_threshold' or _loop_rule.get('min_confidence') is not None:",
            "    df = strip_boxes_below_confidence(df, categories=_loop_rule.get('categories', []), "
            "min_confidence=float(_loop_rule.get('min_confidence', (_loop_rule.get('confidence_range') or [0, 1])[0])), "
            "positions=_loop_rule.get('positions') or None)",
            "else:",
            "    df = filter_df_by_ext(df, "
            "categories=_loop_rule.get('categories', []), "
            "confidence_range=tuple(_loop_rule.get('confidence_range', [0, 1])), "
            "random_drop_ratio=_loop_rule.get('random_drop_ratio', 1.0), "
            "positions=_loop_rule.get('positions') or None)",
        ]
    cats = p.get('categories') or []
    cr = p.get('confidence_range') or [0, 1]
    ratio = p.get('random_drop_ratio', 1.0)
    return [
        f"df = filter_df_by_ext(df, categories={_repr_value(cats)}, "
        f"confidence_range=({cr[0]}, {cr[1]}), random_drop_ratio={ratio})"
    ]


def _compile_action(node, templates, tpl_defs, tpl_order, errors, in_rules_loop=False):
    t = node.get('type', '')
    nid = node.get('id', '?')
    p = node.get('params') or {}
    lines = []

    if t.startswith('template.') or node.get('template_id'):
        tpl_id = node.get('template_id') or t.replace('template.', '', 1)
        if tpl_id == 'random_sample':
            return [
                f'# [{nid}] 随机采样',
                f'df = {RANDOM_SAMPLE_FUNC}(df)',
            ]
        tpl = templates.get(tpl_id)
        if not tpl:
            errors.append(f'[{nid}] 模板不存在: {tpl_id}')
            return [f'# missing template {tpl_id}']
        fn_key = f'{tpl_id}:{nid}'
        fn = f'_tpl_{_sanitize_func_name(tpl_id)}_{_sanitize_func_name(nid)}'
        if fn_key not in tpl_defs:
            code = tpl.get('python_code', '')
            if code == '__CUSTOM__':
                code = p.get('code', 'def filter(df, params):\n    return df')
            m = re.search(r'def\s+(\w+)\s*\(', code)
            if not m:
                errors.append(f'[{nid}] 模板无效: {tpl_id}')
                return [f'# invalid template {tpl_id}']
            tpl_defs[fn_key] = code.replace(f'def {m.group(1)}', f'def {fn}', 1)
            tpl_order.append(fn_key)
        lines += [f'# [{nid}] {tpl.get("name", tpl_id)}', f'df = {fn}(df, {_repr_value(p)})']
        return lines

    if t == 'builtin.filter_df_by_ext':
        fl = _compile_filter(p, in_rules_loop)
        if isinstance(fl, str):
            fl = fl.split('\n')
        return [f'# [{nid}] filter', *fl]
    if t == 'builtin.remove_empty_ext_rows':
        return [f'# [{nid}] remove_empty', 'df = remove_empty_ext_rows(df)']
    if t == 'builtin.view':
        lines = [f'# [{nid}] view']
        label = (p.get('label') or '').strip()
        if label:
            lines.append(f'view(df, description={label!r})')
        else:
            lines.append('view(df)')
        return lines
    if t == 'builtin.count_category_boxes':
        return [f'# [{nid}] count_boxes', 'view(count_category_boxes(df))']

    errors.append(f'[{nid}] 未知节点: {t}')
    return [f'# unknown {t}']


def _compile_container(node, templates, tpl_defs, tpl_order, errors, in_rules_loop=False,
                       delegate_rules_loop=False, entry_func=PROCESS_FUNC):
    t = node.get('type', '')
    nid = node.get('id', '?')
    p = node.get('params') or {}

    if t == 'control.if':
        if _is_redundant_sample_if(node):
            return _compile_nodes(
                node.get('then') or [], templates, tpl_defs, tpl_order, errors, in_rules_loop,
                delegate_rules_loop=delegate_rules_loop, entry_func=entry_func, indent=0,
            )
        lines = [f'# [{nid}] if', f'if {_compile_condition(p)}:']
        then_body = _compile_nodes(node.get('then') or [], templates, tpl_defs, tpl_order, errors, in_rules_loop,
                                   delegate_rules_loop=delegate_rules_loop, entry_func=entry_func, indent=0)
        lines += ['    ' + ln for ln in then_body] if then_body else ['    pass']
        else_nodes = node.get('else') or []
        if else_nodes:
            lines.append('else:')
            else_body = _compile_nodes(else_nodes, templates, tpl_defs, tpl_order, errors, in_rules_loop,
                                       delegate_rules_loop=delegate_rules_loop, entry_func=entry_func, indent=0)
            lines += ['    ' + ln for ln in else_body] if else_body else ['    pass']
        return lines

    if t == 'control.loop':
        mode = p.get('loop_mode', 'rules')
        body = node.get('body') or []
        lines = [f'# [{nid}] loop({mode})']

        if mode == 'count':
            count = max(1, int(p.get('count', 1)))
            lines.append(f'for _loop_i in range({count}):')
            inner = _compile_nodes(body, templates, tpl_defs, tpl_order, errors, False,
                                   delegate_rules_loop=delegate_rules_loop, entry_func=entry_func, indent=0)
            lines += ['    ' + ln for ln in inner] if inner else ['    pass']
            return lines

        if mode == 'while_rows':
            op = OP_MAP.get(p.get('op', 'gt'), '>')
            value = int(p.get('value', 0))
            cap = max(1, int(p.get('max_iterations', 50)))
            lines += [f'_loop_guard = 0', f'while len(df) {op} {value} and _loop_guard < {cap}:', '    _loop_guard += 1']
            inner = _compile_nodes(body, templates, tpl_defs, tpl_order, errors, False,
                                   delegate_rules_loop=delegate_rules_loop, entry_func=entry_func, indent=0)
            lines += ['    ' + ln for ln in inner] if inner else ['    pass']
            return lines

        rules = p.get('rules') or []
        if not rules:
            lines.append('pass')
            return lines
        if delegate_rules_loop and entry_func == PROCESS_FUNC:
            lines.append(f'df = {FILTER_RULES_FUNC}(df)')
            return lines
        lines += [f'_rules = {_repr_value(rules)}', 'for _loop_rule in _rules:']
        inner = _compile_nodes(body, templates, tpl_defs, tpl_order, errors, in_rules_loop=True, indent=0)
        lines += ['    ' + ln for ln in inner] if inner else ['    pass']
        return lines

    return _compile_action(node, templates, tpl_defs, tpl_order, errors, in_rules_loop)


def _compile_nodes(nodes, templates, tpl_defs, tpl_order, errors, in_rules_loop=False, indent=1,
                   delegate_rules_loop=False, entry_func=PROCESS_FUNC):
    lines = []
    for node in nodes or []:
        t = node.get('type', '')
        if is_container_type(t):
            block = _compile_container(node, templates, tpl_defs, tpl_order, errors, in_rules_loop,
                                       delegate_rules_loop=delegate_rules_loop, entry_func=entry_func)
        else:
            block = _compile_action(node, templates, tpl_defs, tpl_order, errors, in_rules_loop)
        lines.extend(block)
    return _indent_lines(lines, indent) if indent else lines


def compile_flow(flow, templates=None, entry_func=PROCESS_FUNC, delegate_rules_loop=False):
    templates = templates or {}
    flow = prepare_flow(flow)
    errors = validate_flow(flow)
    nodes = flow.get('nodes') or []

    if not nodes:
        return {
            'python_code': f'def {entry_func}(df):\n    return df\n',
            'valid': len(errors) == 0,
            'errors': errors,
            'template_helpers': [],
        }

    tpl_defs = {}
    tpl_order = []
    compile_errors = list(errors)
    body = _compile_nodes(nodes, templates, tpl_defs, tpl_order, compile_errors, indent=1,
                          delegate_rules_loop=delegate_rules_loop, entry_func=entry_func)
    body.append('    return df')

    helpers = '\n\n'.join(tpl_defs[k] for k in tpl_order)
    process_body = '\n'.join(body)
    if helpers:
        code = f'{helpers}\n\n\ndef {entry_func}(df):\n{process_body}\n'
    else:
        code = f'def {entry_func}(df):\n{process_body}\n'

    return {
        'python_code': code,
        'valid': len(compile_errors) == 0,
        'errors': compile_errors,
        'template_helpers': tpl_order,
    }


def compile_filter_rules(flow, templates=None):
    """仅将筛选规则循环编译为 apply_filter_rules(df)。"""
    return compile_flow(flow, templates, entry_func=FILTER_RULES_FUNC)


def compile_process_data(flow, templates=None):
    """编译 process_data：规则循环委托给 apply_filter_rules。"""
    return compile_flow(flow, templates, entry_func=PROCESS_FUNC, delegate_rules_loop=True)


def flow_has_rules_loop(flow):
    """flow 是否包含可提取的筛选规则循环。"""
    return bool(extract_rules_compile_flow(flow).get('nodes'))


def _looks_legacy_compiled_python(code):
    code = (code or '').strip()
    return bool(code) and ('_tpl_' in code or 'for _loop_rule in _rules' in code)


def _uses_legacy_sampling_in_process(code: str) -> bool:
    code = code or ''
    if re.search(r'_tpl_random_sample', code):
        return True
    if re.search(r'\.sample\s*\(', code):
        return True
    if re.search(r'if\s+len\s*\(\s*df\s*\)\s*>', code) and RANDOM_SAMPLE_FUNC in code:
        return True
    return False


def normalize_strategy(strategy, templates=None):
    """加载/返回前拆分 filter_rules_code 与手写 process_data。"""
    s = dict(strategy or {})
    templates = templates or {}
    mode = s.get('filter_mode', 'flow')
    flow = s.get('flow') or {}

    if s.get('source_python_code'):
        s['python_code'] = s['source_python_code']

    sample_from_flow = compile_sample_code(flow, templates) if flow.get('nodes') else ''
    if sample_from_flow:
        s['sample_code'] = sample_from_flow

    if mode in ('flow', 'split', 'rules', 'code') and flow.get('nodes'):
        has_rules = flow_has_rules_loop(flow)
        py = (s.get('python_code') or '').strip()

        if has_rules:
            rules_code = (s.get('filter_rules_code') or '').strip()
            if not rules_code:
                rules_flow = extract_rules_compile_flow(flow)
                compiled = compile_filter_rules(rules_flow, templates)
                if compiled['valid'] and compiled['python_code'].strip():
                    s['filter_rules_code'] = compiled['python_code']

            needs_resync = (
                _looks_legacy_compiled_python(py)
                or _uses_legacy_sampling_in_process(py)
                or 'def apply_filter_rules' in py
                or 'for _loop_rule in _rules' in py
                or not py
                or (f'{FILTER_RULES_FUNC}(df)' not in py and s.get('filter_rules_code'))
            )
            if needs_resync:
                proc = compile_process_data(flow, templates)
                if proc['valid'] and proc['python_code'].strip():
                    s['python_code'] = proc['python_code']
                if s.get('filter_rules_code'):
                    s['filter_mode'] = 'split'
                    s.pop('source_python_code', None)
        else:
            stub = f'def {PROCESS_FUNC}(df):\n    return df'
            needs_resync = (
                not py
                or py.strip() == stub
                or _looks_legacy_compiled_python(py)
                or _uses_legacy_sampling_in_process(py)
            )
            if needs_resync:
                proc = compile_process_data(flow, templates)
                if proc['valid'] and proc['python_code'].strip():
                    s['python_code'] = proc['python_code']
                    s['filter_mode'] = 'code'
            s.pop('filter_rules_code', None)
            s.pop('source_python_code', None)

    return s


def build_random_sample_function(max_rows=300, random_seed=42):
    """生成可编辑的随机采样函数（参数由 UI 同步到此函数签名）。"""
    max_rows = int(max_rows)
    random_seed = int(random_seed)
    return (
        f'def {RANDOM_SAMPLE_FUNC}(df, max_rows={max_rows}, random_seed={random_seed}):\n'
        f'    """随机采样；行数不足时返回全部。"""\n'
        f'    max_rows = int(max_rows)\n'
        f'    seed = int(random_seed)\n'
        f'    if max_rows <= 0 or len(df) <= max_rows:\n'
        f'        return df.reset_index(drop=True)\n'
        f'    return df.sample(n=max_rows, random_state=seed).reset_index(drop=True)\n'
    )


def compile_sample_code(flow, templates=None):
    """从 flow 提取 random_sample 节点参数，生成采样函数定义。"""
    _ = templates
    max_rows, seed = 300, 42
    found = False
    for node in _walk_flow_nodes((flow or {}).get('nodes') or []):
        t = node.get('type') or ''
        tid = node.get('template_id') or ''
        if t == 'template.random_sample' or tid == 'random_sample':
            p = node.get('params') or {}
            max_rows = int(p.get('max_rows', 300))
            seed = int(p.get('random_seed', 42))
            found = True
    if not found:
        return ''
    return build_random_sample_function(max_rows, seed)


def combine_python_code(filter_rules_code='', process_code='', sample_code=''):
    """合并规则函数 + 采样函数 + 手写的 process_data。"""
    return combine_execution_python(filter_rules_code, sample_code, process_code)


def combine_execution_python(filter_rules_code='', sample_code='', process_code=''):
    """合并 apply_filter_rules + apply_random_sample_rows + process_data。"""
    rules = (filter_rules_code or '').strip()
    sample = (sample_code or '').strip()
    proc = (process_code or '').strip()
    if not rules and not sample and not proc:
        return f'def {PROCESS_FUNC}(df):\n    return df\n'
    if rules and not proc:
        proc = f'def {PROCESS_FUNC}(df):\n    return {FILTER_RULES_FUNC}(df)\n'
    parts = [rules, sample, proc]
    merged = '\n\n'.join(p for p in parts if p)
    return merged + ('\n' if merged else '')


def extract_rules_compile_flow(flow):
    """从完整 flow 中提取仅含规则循环的子 flow，用于编译 apply_filter_rules。"""
    flow = prepare_flow(flow)
    nodes = flow.get('nodes') or []

    def inspect_loop(node):
        if node.get('type') != 'control.loop':
            return None
        if (node.get('params') or {}).get('loop_mode', 'rules') != 'rules':
            return None
        body = node.get('body') or []
        if not any(n.get('type') == 'builtin.filter_df_by_ext' for n in body):
            return None
        return node

    def walk(node_list):
        for node in node_list or []:
            hit = inspect_loop(node)
            if hit:
                return hit
            for branch in ('then', 'else', 'body'):
                for child in node.get(branch) or []:
                    hit = walk([child])
                    if hit:
                        return hit
        return None

    if len(nodes) == 1:
        hit = inspect_loop(nodes[0])
        if hit:
            return {'version': flow.get('version', 2), 'nodes': [hit]}

    loop = walk(nodes)
    if loop:
        return {'version': flow.get('version', 2), 'nodes': [loop]}
    return {'version': flow.get('version', 2), 'nodes': []}


def resolve_strategy_python(strategy, templates=None):
    """Strategy v2：规则 → apply_filter_rules；process_data 由用户手写或从 flow 编译。"""
    templates = templates or {}
    mode = strategy.get('filter_mode', 'flow')
    flow = strategy.get('flow') or {}
    has_rules = flow_has_rules_loop(flow) if flow.get('nodes') else False

    if mode in ('flow', 'split', 'rules'):
        rules_code = (strategy.get('filter_rules_code') or '').strip()
        process_code = (strategy.get('python_code') or '').strip()

        if not rules_code and has_rules:
            rules_flow = extract_rules_compile_flow(flow)
            compiled = compile_filter_rules(rules_flow, templates)
            if not compiled['valid']:
                raise ValueError('筛选规则编译失败: ' + '; '.join(compiled['errors']))
            rules_code = compiled['python_code']

        sample_code = (strategy.get('sample_code') or '').strip()
        if not sample_code and flow.get('nodes'):
            sample_code = compile_sample_code(flow, templates)

        if not process_code and flow.get('nodes'):
            proc = compile_process_data(flow, templates)
            if not proc['valid']:
                raise ValueError('process_data 编译失败: ' + '; '.join(proc['errors']))
            process_code = proc['python_code']

        if rules_code or sample_code or process_code:
            return combine_execution_python(
                rules_code if has_rules else '',
                sample_code,
                process_code,
            ), 'flow'
        raise ValueError('筛选规则为空且未提供 process_data 代码')

    code = (strategy.get('python_code') or '').strip()
    if code:
        return code, 'code'

    if flow.get('nodes'):
        proc = compile_process_data(flow, templates)
        if proc['valid'] and proc['python_code'].strip():
            return proc['python_code'], 'flow'

    return '', 'empty'


_FLOW_BRANCH_KEYS = ('then', 'else', 'body')


def _walk_flow_nodes(nodes):
    for node in nodes or []:
        yield node
        for key in _FLOW_BRANCH_KEYS:
            yield from _walk_flow_nodes(node.get(key) or [])


def _flow_has_random_sample(flow):
    if not flow:
        return False
    for node in _walk_flow_nodes(flow.get('nodes') or []):
        t = node.get('type') or ''
        tid = node.get('template_id') or ''
        if t == 'template.random_sample' or tid == 'random_sample':
            return True
    return False


def has_inline_sampling(python_code='', flow=None):
    """process_data / flow 已含随机采样时，跳过查询后的二次采样。"""
    code = (python_code or '').strip()
    if code:
        if re.search(r'\.sample\s*\(', code):
            return True
        if re.search(r'_tpl_random_sample', code):
            return True
        if re.search(r'\bapply_random_sample_rows\s*\(', code):
            return True
    if _flow_has_random_sample(flow or {}):
        return True
    return False
