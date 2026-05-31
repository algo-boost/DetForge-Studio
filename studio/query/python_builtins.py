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
        obj = json.loads(ext_value) if isinstance(ext_value, str) else ext_value
        if isinstance(obj, dict):
            preds = obj.get('original_predictions', [])
        elif isinstance(obj, list):
            preds = obj
        else:
            preds = []
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
            name = pred.get('name', '')
            conf = float(pred.get('confidence', 0) or 0)
            if name in categories and conf < min_confidence:
                continue
            kept.append(pred)
        obj['original_predictions'] = kept
        return _serialize_ext(obj)
    except Exception:
        return ext_val


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
            name = pred.get('name', '')
            conf = float(pred.get('confidence', 0) or 0)
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
                counter[pred.get('name', '未知')] += 1
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


def apply_random_sample_rows(df, max_rows=300, random_seed=42):
    """在 DataFrame 上随机采样；行数不足时返回全部。"""
    max_rows = int(max_rows)
    seed = int(random_seed)
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
    """构建用户 Python 代码的执行命名空间。"""
    ns = {
        'pd': pd,
        'json': json,
        'view': view,
        'info': info,
        'describe_df': describe_df,
        'parse_ext': parse_ext,
        'is_ext_empty': is_ext_empty,
        'filter_df_by_ext': filter_df_by_ext,
        'strip_boxes_below_confidence': strip_boxes_below_confidence,
        'remove_empty_ext_rows': remove_empty_ext_rows,
        'count_category_boxes': count_category_boxes,
        'apply_random_sample_rows': apply_random_sample_rows,
        'stratified_sample_by_type': stratified_sample_by_type,
    }
    if extra:
        ns.update(extra)
    return ns
