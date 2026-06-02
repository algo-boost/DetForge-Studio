"""策略可声明加载的 Python 预设函数包（python_presets）。"""
from __future__ import annotations

import re
from typing import Any, Callable

from studio.query import python_builtins as pb

# 预设包：策略 python_presets 列表可引用 id
PRESET_GROUPS: dict[str, dict[str, Any]] = {
    'core': {
        'label': '核心',
        'description': 'pandas / JSON / ext 解析（始终加载）',
        'always': True,
        'functions': [],
    },
    'observe': {
        'label': '观察调试',
        'description': 'view / info / 统计弹窗',
        'functions': ['view', 'info', 'describe_df', 'count_category_boxes'],
    },
    'filter': {
        'label': '缺陷筛选',
        'description': '按 ext 框筛选、剔除低置信、移除空行',
        'functions': [
            'filter_df_by_ext',
            'select_df_rows_by_rules_union',
            'strip_boxes_below_confidence',
            'remove_empty_ext_rows',
        ],
    },
    'sampling': {
        'label': '采样',
        'description': '随机采样与分层采样（参数走 SAMPLE_SIZE / RANDOM_SEED 等 env）',
        'functions': ['apply_random_sample_rows', 'stratified_sample_by_type'],
        'env_keys': ['SAMPLE_SIZE', 'RANDOM_SEED'],
        'env_schema': [
            {
                'key': 'SAMPLE_SIZE',
                'label': '随机采样数量',
                'type': 'number',
                'default': '',
                'description': '留空表示不采样；仅勾选预设「采样」时出现',
            },
            {
                'key': 'RANDOM_SEED',
                'label': '随机种子',
                'type': 'number',
                'default': '42',
            },
        ],
    },
}

# Flow 块 / 内置节点 → 预设包（用于决定是否合并该块的 env 参数）
FLOW_BLOCK_PRESET: dict[str, str] = {
    'random_sample': 'sampling',
    'category_filter': 'filter',
    'confidence_filter': 'filter',
    'dedup': 'filter',
    'builtin.filter_df_by_ext': 'filter',
    'builtin.remove_empty_ext_rows': 'filter',
    'builtin.strip_boxes_below_confidence': 'filter',
}

# 函数名 → 文档（供 API / 前端帮助）
FUNCTION_DOCS: dict[str, str] = {
    'view': '弹窗查看 DataFrame',
    'info': '打印 DataFrame 基本信息',
    'describe_df': '弹窗查看统计描述',
    'parse_ext': '解析 ext 为 predictions 列表',
    'is_ext_empty': '判断 ext 检测框是否为空',
    'filter_df_by_ext': '按类别+置信区间随机剔除框（改 ext）',
    'select_df_rows_by_rules_union': '捞图：按规则保留整行，不删框',
    'strip_boxes_below_confidence': '低于阈值剔除框',
    'remove_empty_ext_rows': '移除无检测框的行',
    'count_category_boxes': '统计各类别框数量',
    'apply_random_sample_rows': '随机采样（env: SAMPLE_SIZE / RANDOM_SEED）',
    'stratified_sample_by_type': '按款型分层采样（env 或参数 n/seed）',
    'get_env': "读取环境变量 get_env('KEY', 'default')",
}

_NAME_RE = re.compile(
    r'\b(' + '|'.join(re.escape(n) for n in FUNCTION_DOCS if n != 'get_env') + r')\s*\(',
)


def list_preset_catalog() -> dict[str, Any]:
    """API：预设包与函数说明。"""
    groups = []
    for gid, meta in PRESET_GROUPS.items():
        groups.append({
            'id': gid,
            'label': meta.get('label', gid),
            'description': meta.get('description', ''),
            'always': bool(meta.get('always')),
            'functions': [
                {'name': fn, 'doc': FUNCTION_DOCS.get(fn, '')}
                for fn in meta.get('functions') or []
            ],
        })
    return {
        'groups': groups,
        'function_docs': FUNCTION_DOCS,
    }


def _expand_group_ids(group_ids: list[str] | None) -> set[str]:
    names: set[str] = set()
    for gid in group_ids or []:
        g = PRESET_GROUPS.get(str(gid).strip())
        if not g:
            continue
        for fn in g.get('functions') or []:
            names.add(str(fn))
    return names


def infer_preset_groups_from_code(*code_parts: str | None) -> list[str]:
    """从 Python 源码推断需要的预设包 id。"""
    text = '\n'.join(p for p in code_parts if p)
    if not text.strip():
        return []
    found = set(_NAME_RE.findall(text))
    groups: list[str] = []
    for gid, meta in PRESET_GROUPS.items():
        if meta.get('always'):
            continue
        fns = set(meta.get('functions') or [])
        if found & fns:
            groups.append(gid)
    return groups


def preset_env_keys_map() -> dict[str, frozenset[str]]:
    """预设包 id → 其专属环境变量 key（未勾选时不应在查询页展示）。"""
    out: dict[str, frozenset[str]] = {}
    for gid, meta in PRESET_GROUPS.items():
        if meta.get('always'):
            continue
        keys = {_norm_env_key(k) for k in (meta.get('env_keys') or [])}
        for row in meta.get('env_schema') or []:
            if isinstance(row, dict) and row.get('key'):
                keys.add(_norm_env_key(row['key']))
        out[gid] = frozenset(keys)
    return out


def _norm_env_key(key: str) -> str:
    return str(key or '').strip().upper()


def explicit_python_presets(strategy: dict | None) -> list[str] | None:
    """策略显式声明的 python_presets；None 表示未声明（可走代码推断）。"""
    strategy = strategy or {}
    explicit = strategy.get('python_presets')
    if explicit is None:
        explicit = strategy.get('preset_functions')
    if isinstance(explicit, list):
        out: list[str] = []
        for item in explicit:
            s = str(item).strip()
            if s and s in PRESET_GROUPS and s not in out:
                out.append(s)
        return out
    return None


def active_presets_for_env_schema(strategy: dict | None) -> list[str]:
    """
    查询页 / env_schema 使用的活跃预设包。
    优先 process_pipeline 步骤中的 preset_group；
    否则显式 python_presets；再否则从代码推断。
    """
    strategy = strategy or {}
    try:
        from studio.flow.process_pipeline import ensure_process_pipeline, preset_groups_from_pipeline
        from studio.query.strategy_loader import get_all_templates

        pipeline = ensure_process_pipeline(strategy, get_all_templates())
        if pipeline:
            groups = preset_groups_from_pipeline(pipeline, get_all_templates())
            if groups:
                return groups
    except Exception:
        pass
    explicit = explicit_python_presets(strategy)
    if explicit is not None:
        return explicit
    return resolve_python_presets(strategy)


def inactive_preset_env_keys(active_preset_ids: list[str] | None) -> frozenset[str]:
    """未勾选预设包所拥有的 env key，应从 schema 中剔除。"""
    active = set(active_preset_ids or [])
    blocked: set[str] = set()
    for gid, keys in preset_env_keys_map().items():
        if gid not in active:
            blocked |= set(keys)
    return frozenset(blocked)


def preset_env_schema_for_active(active_preset_ids: list[str] | None) -> list[dict[str, Any]]:
    """按活跃预设包合并默认 env_schema 行。"""
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for gid in active_preset_ids or []:
        meta = PRESET_GROUPS.get(gid) or {}
        for row in meta.get('env_schema') or []:
            if not isinstance(row, dict):
                continue
            key = _norm_env_key(row.get('key'))
            if not key or key in seen:
                continue
            seen.add(key)
            rows.append({**row, 'key': key})
    return rows


def flow_node_preset_id(node: dict | None) -> str | None:
    """Flow 节点对应的预设包 id（无则 None）。"""
    if not isinstance(node, dict):
        return None
    tpl_id = node.get('template_id') or ''
    node_type = str(node.get('type') or '')
    if not tpl_id and node_type.startswith('template.'):
        tpl_id = node_type.replace('template.', '', 1)
    if tpl_id and tpl_id in FLOW_BLOCK_PRESET:
        return FLOW_BLOCK_PRESET[tpl_id]
    if node_type in FLOW_BLOCK_PRESET:
        return FLOW_BLOCK_PRESET[node_type]
    return None


def resolve_python_presets(strategy: dict | None) -> list[str]:
    """解析策略应加载的预设包（显式声明优先，否则从代码推断）。"""
    strategy = strategy or {}
    explicit = strategy.get('python_presets')
    if explicit is None:
        explicit = strategy.get('preset_functions')
    if isinstance(explicit, list) and explicit:
        out: list[str] = []
        for item in explicit:
            s = str(item).strip()
            if not s:
                continue
            if s in PRESET_GROUPS:
                if s not in out:
                    out.append(s)
            elif s in FUNCTION_DOCS and s != 'get_env':
                for gid, meta in PRESET_GROUPS.items():
                    if s in (meta.get('functions') or []) and gid not in out:
                        out.append(gid)
        return out

    inferred = infer_preset_groups_from_code(
        strategy.get('python_code'),
        strategy.get('filter_rules_code'),
        strategy.get('sample_code'),
    )
    flow = strategy.get('flow') or {}
    if flow.get('nodes'):
        try:
            from studio.flow.flow_compiler import compile_sample_code, compile_filter_rules, compile_process_data
            from studio.query.strategy_loader import get_all_templates

            tpl = get_all_templates()
            inferred.extend(infer_preset_groups_from_code(
                compile_filter_rules(flow, tpl).get('python_code'),
                compile_sample_code(flow, tpl),
                compile_process_data(flow, tpl).get('python_code'),
            ))
        except Exception:
            pass
    seen: list[str] = []
    for gid in inferred:
        if gid not in seen:
            seen.append(gid)
    return seen


def _callable_map() -> dict[str, Callable]:
    return {
        'view': pb.view,
        'info': pb.info,
        'describe_df': pb.describe_df,
        'parse_ext': pb.parse_ext,
        'is_ext_empty': pb.is_ext_empty,
        'filter_df_by_ext': pb.filter_df_by_ext,
        'select_df_rows_by_rules_union': pb.select_df_rows_by_rules_union,
        'strip_boxes_below_confidence': pb.strip_boxes_below_confidence,
        'remove_empty_ext_rows': pb.remove_empty_ext_rows,
        'count_category_boxes': pb.count_category_boxes,
        'apply_random_sample_rows': pb.apply_random_sample_rows,
        'stratified_sample_by_type': pb.stratified_sample_by_type,
    }


def build_execution_namespace(
    env_context: dict | None,
    *,
    strategy: dict | None = None,
    python_presets: list[str] | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    """构建用户 Python 执行命名空间（含 get_env 与策略声明的预设函数）。"""
    from studio.query.env_context import normalize_env_dict

    ctx = normalize_env_dict(env_context)

    def _get_env(key, default=''):
        return str(ctx.get(str(key).upper(), default))

    explicit = explicit_python_presets(strategy) if strategy else None
    pipeline_fn_names: set[str] = set()
    if strategy:
        try:
            from studio.flow.process_pipeline import ensure_process_pipeline, inject_functions_from_pipeline
            from studio.query.strategy_loader import get_all_templates

            pipe = ensure_process_pipeline(strategy, get_all_templates())
            if pipe:
                pipeline_fn_names = set(inject_functions_from_pipeline(pipe, get_all_templates()))
        except Exception:
            pass

    if python_presets is not None:
        group_ids = list(python_presets)
    elif pipeline_fn_names:
        group_ids = active_presets_for_env_schema(strategy)
    elif explicit is not None:
        group_ids = explicit
    elif strategy is not None:
        group_ids = resolve_python_presets(strategy)
    else:
        group_ids = infer_preset_groups_from_code(code)

    fn_names = _expand_group_ids(group_ids) | pipeline_fn_names
    if explicit is None and not pipeline_fn_names:
        fn_names |= set(_NAME_RE.findall(code or ''))
        if strategy and 'apply_filter_rules' in (strategy.get('python_code') or ''):
            fn_names |= _expand_group_ids(['filter'])
        if strategy and 'apply_random_sample_rows' in (strategy.get('python_code') or ''):
            fn_names.add('apply_random_sample_rows')

    cmap = _callable_map()
    extra: dict[str, Any] = {
        'ENV': dict(ctx),
        'get_env': _get_env,
        'env': _get_env,
    }

    if 'apply_random_sample_rows' in fn_names:

        def _apply_random_sample_rows(df, max_rows=None, random_seed=None):
            return pb.apply_random_sample_rows(
                df, max_rows=max_rows, random_seed=random_seed, env=ctx,
            )

        extra['apply_random_sample_rows'] = _apply_random_sample_rows

    for name in fn_names:
        if name in cmap and name not in extra:
            extra[name] = cmap[name]

    return pb.build_minimal_python_namespace(extra)
