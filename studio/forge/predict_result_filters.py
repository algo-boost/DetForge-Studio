"""predict_result 筛选：按 ext.original_predictions 类别/置信度过滤，并同步 box_count/max_score。"""
from __future__ import annotations

import json

from studio.query.python_builtins import is_ext_empty, parse_ext


def _is_na(val):
    if val is None:
        return True
    try:
        import math
        return isinstance(val, float) and math.isnan(val)
    except (TypeError, ValueError):
        return False


def _serialize_ext(obj):
    return json.dumps(obj, ensure_ascii=False)


def _coerce_ext_object(ext_val):
    """将库表 ext（str / dict / bytes / 单引号 Python 字面量）转为 dict。"""
    if _is_na(ext_val):
        return {'original_predictions': []}
    if isinstance(ext_val, bytes):
        ext_val = ext_val.decode('utf-8', errors='replace')
    if isinstance(ext_val, str):
        s = ext_val.strip()
        if not s:
            return {'original_predictions': []}
        try:
            obj = json.loads(s)
        except json.JSONDecodeError:
            try:
                import ast
                obj = ast.literal_eval(s)
            except Exception:
                return {'original_predictions': []}
    elif isinstance(ext_val, dict):
        obj = ext_val
    elif isinstance(ext_val, list):
        return {'original_predictions': ext_val}
    else:
        return {'original_predictions': []}
    if not isinstance(obj, dict):
        if isinstance(obj, list):
            return {'original_predictions': obj}
        return {'original_predictions': []}
    return obj


def normalize_ext_value(ext_val):
    """统一 ext 为含 original_predictions 的 JSON 字符串。"""
    obj = _coerce_ext_object(ext_val)
    preds = obj.get('original_predictions')
    if preds is None:
        preds = obj.get('predictions') or []
    if not isinstance(preds, list):
        preds = []
    obj['original_predictions'] = preds
    return _serialize_ext(obj)


def ext_has_matching_prediction(ext_val, categories=None, min_confidence=None, max_confidence=None):
    """判断 ext 是否含满足类别与置信度区间的预测框。"""
    cats = [str(c).strip() for c in (categories or []) if str(c).strip()]
    if not cats and min_confidence is None and max_confidence is None:
        return True
    try:
        min_c = float(min_confidence) if min_confidence is not None else None
    except (TypeError, ValueError):
        min_c = None
    try:
        max_c = float(max_confidence) if max_confidence is not None else None
    except (TypeError, ValueError):
        max_c = None

    for pred in parse_ext(ext_val):
        if not isinstance(pred, dict):
            continue
        name = str(pred.get('name') or pred.get('category') or '').strip()
        if cats and name not in cats:
            continue
        try:
            conf = float(pred.get('confidence', pred.get('score', 0)) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if min_c is not None and conf < min_c:
            continue
        if max_c is not None and conf > max_c:
            continue
        return True
    return False


def metrics_from_ext(ext_val):
    preds = [p for p in parse_ext(ext_val) if isinstance(p, dict)]
    if not preds:
        return 0, None
    scores = []
    for p in preds:
        try:
            scores.append(float(p.get('confidence', p.get('score', 0)) or 0))
        except (TypeError, ValueError):
            pass
    return len(preds), (max(scores) if scores else None)


def append_predict_result_filter_sql(where, args, filters=None):
    """向 WHERE 追加 predict_result 条件（含 ext 内类别/置信度）。"""
    f = filters or {}

    if f.get('min_box_count') is not None and str(f.get('min_box_count')).strip() != '':
        where.append('box_count >= %s')
        args.append(int(f['min_box_count']))
    if f.get('only_with_boxes'):
        where.append('box_count > 0')
    if f.get('zero_boxes_only'):
        where.append('box_count = 0')
    if f.get('product_type'):
        where.append('product_type LIKE %s')
        args.append(f'%{f["product_type"]}%')
    if f.get('min_max_score') is not None:
        where.append('max_score IS NOT NULL AND max_score >= %s')
        args.append(float(f['min_max_score']))
    if f.get('max_max_score') is not None:
        where.append('(max_score IS NULL OR max_score <= %s)')
        args.append(float(f['max_max_score']))
    if f.get('q'):
        where.append('img_path LIKE %s')
        args.append(f'%{f["q"]}%')
    if f.get('product_no'):
        where.append('product_no LIKE %s')
        args.append(f'%{f["product_no"]}%')

    categories = _parse_categories(f.get('categories'))
    min_pred = f.get('min_pred_confidence')
    max_pred = f.get('max_pred_confidence')
    if categories or min_pred is not None or max_pred is not None:
        _append_ext_prediction_sql(where, args, categories, min_pred, max_pred)


def _parse_categories(raw):
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(c).strip() for c in raw if str(c).strip()]
    text = str(raw).strip()
    if not text:
        return []
    return [p.strip() for p in text.replace('，', ',').split(',') if p.strip()]


def _append_ext_prediction_sql(where, args, categories, min_confidence=None, max_confidence=None):
    cats = _parse_categories(categories)
    try:
        min_c = float(min_confidence) if min_confidence is not None and str(min_confidence).strip() != '' else None
    except (TypeError, ValueError):
        min_c = None
    try:
        max_c = float(max_confidence) if max_confidence is not None and str(max_confidence).strip() != '' else None
    except (TypeError, ValueError):
        max_c = None

    if min_c is not None or max_c is not None:
        parts = [
            "EXISTS (SELECT 1 FROM JSON_TABLE(ext, '$.original_predictions[*]' "
            "COLUMNS (name VARCHAR(128) PATH '$.name', confidence DOUBLE PATH '$.confidence')) AS jt "
            "WHERE 1=1",
        ]
        if cats:
            placeholders = ','.join(['%s'] * len(cats))
            parts.append(f' AND jt.name IN ({placeholders})')
            args.extend(cats)
        if min_c is not None:
            parts.append(' AND jt.confidence >= %s')
            args.append(min_c)
        if max_c is not None:
            parts.append(' AND jt.confidence <= %s')
            args.append(max_c)
        parts.append(')')
        where.append(''.join(parts))
        return

    if not cats:
        return
    or_parts = []
    for cat in cats:
        or_parts.append(
            "JSON_SEARCH(ext, 'one', %s, NULL, '$.original_predictions[*].name') IS NOT NULL",
        )
        args.append(cat)
    where.append(f'({" OR ".join(or_parts)})')


def normalize_filter_dict(raw):
    """合并 API/前端传入的筛选参数。"""
    if not raw:
        return {}
    f = dict(raw)
    if f.get('only_with_boxes') in (True, '1', 'true', 'yes', 1):
        f['only_with_boxes'] = True
    elif 'only_with_boxes' in f:
        f.pop('only_with_boxes', None)
    if f.get('zero_boxes_only') in (True, '1', 'true', 'yes', 1):
        f['zero_boxes_only'] = True
    elif 'zero_boxes_only' in f:
        f.pop('zero_boxes_only', None)
    cats = _parse_categories(f.get('categories'))
    if cats:
        f['categories'] = cats
    else:
        f.pop('categories', None)
    return f


def prepare_predict_result_df(df):
    """查询/策略执行前：规范化 ext，保证后续 Python 规则可解析。"""
    if df is None or getattr(df, 'empty', True) or 'ext' not in df.columns:
        return df
    out = df.copy()
    for idx in out.index:
        out.at[idx, 'ext'] = normalize_ext_value(out.at[idx, 'ext'])
    return out


def hydrate_predict_result_df(df):
    """确保含 ext 列并规范化；SQL 未选出 ext 时按 id 回表补全。"""
    if df is None or getattr(df, 'empty', True):
        return df
    if 'ext' not in df.columns and 'id' in df.columns:
        from studio.forge import forge_db

        ids = []
        for raw in df['id'].dropna().unique():
            try:
                ids.append(int(raw))
            except (TypeError, ValueError):
                pass
        ext_map = forge_db.fetch_predict_ext_by_ids(ids)
        if ext_map:
            out = df.copy()
            out['ext'] = out['id'].map(lambda x: ext_map.get(int(x)) if not _is_na(x) else None)
            df = out
    return prepare_predict_result_df(df)


def predict_filter_warnings(df, *, data_source='', sql_had_ext=True, python_ran=False):
    """预测结果表 + 规则筛选时的可执行提示（供 API 返回）。"""
    if (data_source or '').strip() != 'predict_result':
        return []
    warnings = []
    if df is None or getattr(df, 'empty', True):
        return warnings
    if not sql_had_ext and 'ext' not in df.columns:
        warnings.append(
            '查询结果不含 ext 列且无法按 id 补全，筛选规则不会按预测框生效。'
            '请使用 SELECT * 或在 SQL 中包含 ext、id。',
        )
    elif not sql_had_ext and 'ext' in df.columns and python_ran:
        warnings.append('SQL 未包含 ext，已按 id 从 predict_result 表补全后应用规则。')
    if python_ran and 'ext' in df.columns:
        try:
            empty_ext = df['ext'].apply(lambda v: is_ext_empty(v)).all()
        except Exception:
            empty_ext = False
        if empty_ext:
            warnings.append('所有行的 ext 均无预测框，类别/置信度规则无法命中。')
    return warnings


def sync_metrics_from_ext(df):
    """根据 ext 内预测框刷新 box_count、max_score。"""
    if df is None or getattr(df, 'empty', True) or 'ext' not in df.columns:
        return df
    out = df.copy()
    for idx in out.index:
        n, mx = metrics_from_ext(out.at[idx, 'ext'])
        out.at[idx, 'box_count'] = n
        out.at[idx, 'max_score'] = mx
    return out


def finalize_predict_result_df(df, *, drop_empty=False):
    """Python 筛选后：同步指标，可选移除无框行。"""
    out = sync_metrics_from_ext(prepare_predict_result_df(df))
    if drop_empty and 'ext' in out.columns:
        mask = out['ext'].apply(lambda v: not is_ext_empty(v))
        out = out.loc[mask].copy().reset_index(drop=True)
    return out


def filter_rows_by_prediction_ext(rows, filters=None):
    """内存行列表按 ext 预测框再滤一层（用于 JSON_TABLE 不可用时的兜底）。"""
    f = normalize_filter_dict(filters)
    cats = f.get('categories') or []
    min_p = f.get('min_pred_confidence')
    max_p = f.get('max_pred_confidence')
    if not cats and min_p is None and max_p is None:
        return rows
    out = []
    for row in rows:
        ext = row.get('ext')
        if ext_has_matching_prediction(ext, cats, min_p, max_p):
            out.append(row)
    return out
