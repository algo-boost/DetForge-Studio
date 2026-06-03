"""Python 筛选预设函数，注入用户代码执行环境。"""
import io
import json
import random

import pandas as pd


def parse_ext(ext_value):
    """解析 ext 字段，返回 original_predictions 列表。"""
    if ext_value is None or (isinstance(ext_value, float) and pd.isna(ext_value)):
        return []
    try:
        from studio.forge.predict_result_filters import _coerce_ext_object
        obj = _coerce_ext_object(ext_value)
        preds = obj.get('original_predictions', [])
        return preds if isinstance(preds, list) else []
    except Exception:
        return []


def is_ext_empty(ext_value):
    """判断 ext 字段中的检测框是否为空。"""
    return len(parse_ext(ext_value)) == 0


def _serialize_ext(obj):
    return json.dumps(obj, ensure_ascii=False)


def _row_matches_positions(row, positions):
    """positions 为空时不限制；df 无 position 列时不限制。"""
    if not positions:
        return True
    if 'position' not in row.index:
        return True
    val = row.get('position')
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    return str(val).strip() in positions


def strip_boxes_below_confidence(df, categories=None, min_confidence=0.0, positions=None):
    """
    产线 / pipeline 语义：指定类别中 confidence 低于 min_confidence 的框直接剔除。
    min_confidence=0.3 表示 0.3 以下全部不要，保留 score >= 0.3 的框。
    """
    if 'ext' not in df.columns:
        return df
    categories = list(categories or [])
    positions = [str(p).strip() for p in (positions or []) if str(p).strip()]
    if not categories:
        return df.copy()
    try:
        min_confidence = float(min_confidence)
    except (TypeError, ValueError):
        min_confidence = 0.0

    result = df.copy()

    for idx in result.index:
        if not _row_matches_positions(result.loc[idx], positions):
            continue
        result.at[idx, 'ext'] = _strip_ext(result.at[idx, 'ext'], categories, min_confidence)

    return result


def _strip_ext(ext_val, categories, min_confidence):
    if ext_val is None or (isinstance(ext_val, float) and pd.isna(ext_val)):
        return ext_val
    try:
        obj = json.loads(ext_val) if isinstance(ext_val, str) else ext_val
        if not isinstance(obj, dict):
            return ext_val
        preds = obj.get('original_predictions', [])
        if not isinstance(preds, list):
            return ext_val
        kept = []
        for pred in preds:
            if not isinstance(pred, dict):
                kept.append(pred)
                continue
            name = str(pred.get('name') or pred.get('category') or '').strip()
            conf = float(pred.get('confidence', pred.get('score', 0)) or 0)
            if name in categories and conf < min_confidence:
                continue
            kept.append(pred)
        obj['original_predictions'] = kept
        return _serialize_ext(obj)
    except Exception:
        return ext_val


def _row_has_matching_pred(ext_val, categories, min_c, max_c):
    for pred in parse_ext(ext_val):
        if not isinstance(pred, dict):
            continue
        name = str(pred.get('name') or pred.get('category') or '').strip()
        conf = float(pred.get('confidence', pred.get('score', 0)) or 0)
        if name in categories and min_c <= conf <= max_c:
            return True
    return False


def _keep_matching_row_by_ratio(random_drop_ratio):
    """
    捞图行级保留概率。random_drop_ratio=0 保留全部匹配行；
    ratio>=1 表示对该规则 100% 纳入匹配行（不删框，legacy 捞图满额）。
    中间值：按比例随机舍弃匹配行（仅丢图，不改 ext）。
    """
    try:
        rdr = float(random_drop_ratio)
    except (TypeError, ValueError):
        rdr = 0.0
    rdr = max(0.0, min(1.0, rdr))
    if rdr >= 1.0:
        return True
    if rdr <= 0.0:
        return True
    return random.random() > rdr


def select_df_rows_by_rules_union(df, rules=None):
    """
    捞图语义：多条规则取并集，保留「至少命中一条规则」的整行，ext 内检测框原样保留。
    产线 min_threshold 规则仍用 strip_boxes_below_confidence 改 ext。
    """
    if 'ext' not in df.columns:
        return df
    rules = list(rules or [])
    if not rules:
        return df.copy()

    working = df.copy()
    keep = set()

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get('confidence_mode') == 'min_threshold' or rule.get('min_confidence') is not None:
            working = strip_boxes_below_confidence(
                working,
                categories=rule.get('categories') or [],
                min_confidence=float(
                    rule.get('min_confidence', (rule.get('confidence_range') or [0, 1])[0])
                ),
                positions=rule.get('positions'),
            )
            continue

        categories = list(rule.get('categories') or [])
        if not categories:
            continue
        cr = rule.get('confidence_range') or [0, 1]
        min_c = _coerce_float(cr[0] if len(cr) > 0 else 0, 0.0)
        max_c = _coerce_float(cr[1] if len(cr) > 1 else 1, 1.0)
        positions = rule.get('positions')
        rdr = rule.get('random_drop_ratio', 0.0)

        for idx in working.index:
            row = working.loc[idx]
            if not _row_matches_positions(row, positions):
                continue
            if not _row_has_matching_pred(row.get('ext'), categories, min_c, max_c):
                continue
            if _keep_matching_row_by_ratio(rdr):
                keep.add(idx)

    if not keep:
        return working.iloc[0:0].copy().reset_index(drop=True)
    return working.loc[sorted(keep)].copy().reset_index(drop=True)


def filter_df_by_ext(df, categories=None, confidence_range=(0, 1), random_drop_ratio=1.0, positions=None):
    """
    对指定类别且落在置信度区间内的框，按 random_drop_ratio 随机筛掉。
    random_drop_ratio=1.0 表示全部筛掉，0.8 表示随机筛掉 80%。
    """
    if 'ext' not in df.columns:
        return df
    categories = list(categories or [])
    positions = [str(p).strip() for p in (positions or []) if str(p).strip()]
    if not categories:
        return df.copy()

    min_c, max_c = confidence_range
    min_c = _coerce_float(min_c, 0.0)
    max_c = _coerce_float(max_c, 1.0)
    random_drop_ratio = max(0.0, min(1.0, float(random_drop_ratio)))
    result = df.copy()

    for idx in result.index:
        if not _row_matches_positions(result.loc[idx], positions):
            continue
        result.at[idx, 'ext'] = _filter_ext(
            result.at[idx, 'ext'], categories, min_c, max_c, random_drop_ratio,
        )

    return result


def _filter_ext(ext_val, categories, min_c, max_c, random_drop_ratio):
    if ext_val is None or (isinstance(ext_val, float) and pd.isna(ext_val)):
        return ext_val
    try:
        obj = json.loads(ext_val) if isinstance(ext_val, str) else ext_val
        if not isinstance(obj, dict):
            return ext_val
        preds = obj.get('original_predictions', [])
        if not isinstance(preds, list):
            return ext_val

        kept = []
        for pred in preds:
            if not isinstance(pred, dict):
                kept.append(pred)
                continue
            name = str(pred.get('name') or pred.get('category') or '').strip()
            conf = float(pred.get('confidence', pred.get('score', 0)) or 0)
            if name in categories and min_c <= conf <= max_c:
                if random.random() < random_drop_ratio:
                    continue
            kept.append(pred)
        obj['original_predictions'] = kept
        return _serialize_ext(obj)
    except Exception:
        return ext_val


def remove_empty_ext_rows(df):
    """移除 ext 中检测框为空的行。"""
    if 'ext' not in df.columns:
        return df
    mask = df['ext'].apply(lambda v: not is_ext_empty(v))
    return df[mask].reset_index(drop=True)


def count_category_boxes(df):
    """统计各类别检测框数量，返回 category / count 列。"""
    from collections import Counter

    counter = Counter()
    if 'ext' not in df.columns:
        return pd.DataFrame(columns=['category', 'count'])
    for ext_val in df['ext']:
        for pred in parse_ext(ext_val):
            if isinstance(pred, dict):
                counter[str(pred.get('name') or pred.get('category') or '未知').strip() or '未知'] += 1
    if not counter:
        return pd.DataFrame(columns=['category', 'count'])
    rows = [{'category': k, 'count': v} for k, v in counter.items()]
    return pd.DataFrame(rows).sort_values('count', ascending=False).reset_index(drop=True)


def _coerce_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _coerce_view_limit(val, default):
    """max_rows / max_cols：数字字符串转 int；非数字字符串返回 None 表示非行数参数。"""
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, int):
        return max(0, val)
    if isinstance(val, float):
        return max(0, int(val))
    if isinstance(val, str):
        s = val.strip()
        if s.isdigit():
            return max(0, int(s))
        return None
    try:
        return max(0, int(val))
    except (TypeError, ValueError):
        return None


def _df_to_view_payload(df, max_rows=None, max_cols=30):
    total_rows, total_cols = len(df), len(df.columns)
    if max_rows is None:
        truncated_rows = False
        display_df = df.copy()
    else:
        max_rows = max(0, int(max_rows))
        truncated_rows = total_rows > max_rows
        display_df = df.head(max_rows) if truncated_rows else df.copy()
    max_cols = _coerce_view_limit(max_cols, 30) or 30
    truncated_cols = total_cols > max_cols
    if truncated_cols:
        display_df = display_df.iloc[:, :max_cols]

    html = display_df.to_html(index=False, border=0, escape=True)
    stats = {
        'total_rows': total_rows,
        'total_cols': total_cols,
        'displayed_rows': len(display_df),
        'displayed_cols': len(display_df.columns),
        'memory_usage': f'{df.memory_usage(deep=True).sum() / 1024:.1f} KB',
    }
    return {
        'html': html,
        'stats': stats,
        'truncated_rows': truncated_rows,
        'truncated_cols': truncated_cols,
    }


def view(df, description=None, *, max_rows=None, max_cols=30):
    """在浏览器弹窗中查看 DataFrame（通过控制台特殊标记传给前端）。

    description: 可选说明，可 positional，如 view(df, '筛选结果')。
    默认显示全部行；view(df, 50) 或 max_rows=50 可限制行数。
    """
    if not isinstance(df, pd.DataFrame):
        print(f'view() 需要 DataFrame，收到: {type(df).__name__}')
        return df

    # view(df, 50) — 第二参数为 int 时视为 max_rows（兼容旧写法）
    if isinstance(description, int) and not isinstance(description, bool):
        max_rows = description
        description = None

    # 误把说明传给 max_rows=...（旧签名遗留）
    if isinstance(max_rows, str) and _coerce_view_limit(max_rows, None) is None:
        if description is None:
            description = max_rows
        max_rows = None

    if max_rows is not None:
        max_rows = _coerce_view_limit(max_rows, None)
    max_cols = _coerce_view_limit(max_cols, 30) or 30

    payload = _df_to_view_payload(df, max_rows=max_rows, max_cols=max_cols)
    if description is not None:
        text = str(description).strip()
        if text:
            payload['description'] = text
    print('__VIEW_DF_START__')
    print(json.dumps(payload, ensure_ascii=False))
    print('__VIEW_DF_END__')
    return df


def info(df):
    """打印 DataFrame 基本信息到控制台。"""
    if not isinstance(df, pd.DataFrame):
        print(f'info() 需要 DataFrame，收到: {type(df).__name__}')
        return
    buf = io.StringIO()
    df.info(buf=buf)
    print(buf.getvalue())


def describe_df(df, description=None):
    """查看 DataFrame 统计描述（弹窗）。"""
    if not isinstance(df, pd.DataFrame):
        print(f'describe_df() 需要 DataFrame，收到: {type(df).__name__}')
        return df
    try:
        desc = df.describe(include='all').transpose()
    except Exception as e:
        print(f'describe 失败: {e}')
        return df
    return view(desc, description=description or '统计描述')


def _resolve_sample_params(max_rows, random_seed, env=None):
    """从 env（SAMPLE_SIZE / RANDOM_SEED）解析采样参数；未配置 SAMPLE_SIZE 时返回 (0, seed) 表示跳过。"""
    ctx = env if env is not None else {}
    if max_rows is None:
        raw = str(ctx.get('SAMPLE_SIZE', '') or '').strip()
        if not raw:
            return 0, int(ctx.get('RANDOM_SEED', 42) or 42)
        try:
            max_rows = int(raw)
        except (TypeError, ValueError):
            return 0, 42
    else:
        max_rows = int(max_rows)
    if random_seed is None:
        try:
            seed = int(ctx.get('RANDOM_SEED', 42) or 42)
        except (TypeError, ValueError):
            seed = 42
    else:
        seed = int(random_seed)
    return max_rows, seed


def apply_random_sample_rows(df, max_rows=None, random_seed=None, env=None):
    """在 DataFrame 上随机采样；默认从环境变量 SAMPLE_SIZE / RANDOM_SEED 读取，未配置则不采样。"""
    max_rows, seed = _resolve_sample_params(max_rows, random_seed, env)
    if max_rows <= 0 or len(df) <= max_rows:
        return df.reset_index(drop=True)
    return df.sample(n=max_rows, random_state=seed).reset_index(drop=True)


def stratified_sample_by_type(df, n=10, type_col='product_type', seed=42):
    """按款型分层采样：每个 type_col 取值随机取 n 行（不足取全部）。

    用于「误检水平评测集」——按 product_type 分层、各层定量随机抽样，
    使评测集覆盖各款型，避免大款型样本压倒小款型。
    """
    n = int(n)
    seed = int(seed)
    if df is None or len(df) == 0 or n <= 0:
        return df.reset_index(drop=True) if isinstance(df, pd.DataFrame) else df
    if type_col not in df.columns:
        # 无分层列时退化为整体随机采样
        return apply_random_sample_rows(df, max_rows=n, random_seed=seed)
    parts = []
    for _, group in df.groupby(df[type_col].fillna('__NA__'), sort=False):
        if len(group) <= n:
            parts.append(group)
        else:
            parts.append(group.sample(n=n, random_state=seed))
    if not parts:
        return df.head(0).reset_index(drop=True)
    return pd.concat(parts).reset_index(drop=True)


def build_python_namespace(extra=None):
    """构建用户 Python 代码的执行命名空间（全量预设，兼容旧调用）。"""
    ns = {
        'pd': pd,
        'json': json,
        'view': view,
        'info': info,
        'describe_df': describe_df,
        'parse_ext': parse_ext,
        'is_ext_empty': is_ext_empty,
        'filter_df_by_ext': filter_df_by_ext,
        'select_df_rows_by_rules_union': select_df_rows_by_rules_union,
        'strip_boxes_below_confidence': strip_boxes_below_confidence,
        'remove_empty_ext_rows': remove_empty_ext_rows,
        'count_category_boxes': count_category_boxes,
        'apply_random_sample_rows': apply_random_sample_rows,
        'stratified_sample_by_type': stratified_sample_by_type,
    }
    if extra:
        ns.update(extra)
    return ns


def build_minimal_python_namespace(extra=None):
    """最小命名空间 + extra（供 python_preset_registry 按策略加载函数）。"""
    ns = {
        'pd': pd,
        'json': json,
        'parse_ext': parse_ext,
        'is_ext_empty': is_ext_empty,
    }
    if extra:
        ns.update(extra)
    return ns
