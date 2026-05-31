"""统一从 ext / infer_raw_result 解析检测框，供 COCO 导出与 API 结果复用。"""
import json

import pandas as pd

from studio.query.python_builtins import parse_ext


def _safe_float(val, default=None):
    try:
        if val is None:
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def bbox_from_prediction(item):
    """从单条 prediction 提取 COCO bbox [x, y, w, h]。"""
    if not isinstance(item, dict):
        return None
    bbox = item.get('bbox')
    if isinstance(bbox, (list, tuple)) and len(bbox) >= 4:
        vals = [_safe_float(bbox[i]) for i in range(4)]
        if None not in vals and vals[2] > 0 and vals[3] > 0:
            return vals
    points = item.get('points') or []
    if points and isinstance(points[0], dict):
        p = points[0]
        x, y, w, h = p.get('x'), p.get('y'), p.get('w'), p.get('h')
        vals = [_safe_float(x), _safe_float(y), _safe_float(w), _safe_float(h)]
        if None not in vals and vals[2] > 0 and vals[3] > 0:
            return vals
    return None


def _parse_infer_raw(raw_val):
    if raw_val is None or (isinstance(raw_val, float) and pd.isna(raw_val)):
        return []
    try:
        obj = json.loads(raw_val) if isinstance(raw_val, str) else raw_val
    except Exception:
        return []
    if not isinstance(obj, dict):
        return []
    preds = obj.get('predictions') or obj.get('original_predictions') or []
    return preds if isinstance(preds, list) else []


def parse_row_predictions(row):
    """解析一行中的全部检测框，优先 ext，再补充 infer_raw_result。"""
    items = []
    seen = set()

    def _add(pred, source):
        if not isinstance(pred, dict):
            return
        name = (pred.get('name') or pred.get('category') or '').strip() or '未知'
        bbox = bbox_from_prediction(pred)
        if not bbox:
            return
        key = (name, round(bbox[0], 2), round(bbox[1], 2), round(bbox[2], 2), round(bbox[3], 2))
        if key in seen:
            return
        seen.add(key)
        score = pred.get('confidence', pred.get('score'))
        items.append({
            'name': name,
            'confidence': _safe_float(score, 0.0),
            'bbox': bbox,
            'defect_type': pred.get('defect_type'),
            'source': source,
        })

    ext_val = row.get('ext') if hasattr(row, 'get') else None
    for pred in parse_ext(ext_val):
        _add(pred, 'ext')

    infer_val = row.get('infer_raw_result') if hasattr(row, 'get') else None
    for pred in _parse_infer_raw(infer_val):
        _add(pred, 'infer_raw_result')

    return items


def build_name2id_maps(id2name):
    id2name = {int(k): v for k, v in (id2name or {}).items()}
    name2id = {v: k for k, v in id2name.items()}
    return id2name, name2id


def resolve_category_id(name, name2id, id2name, categories_out):
    """未知类别动态注册到 categories 列表；仅「未知」等占位名才回退到「其他」。"""
    name = (name or '').strip() or '未知'
    if name in name2id:
        return name2id[name]
    if name in ('未知', 'unknown', '其他'):
        for fallback in ('其他', '未知', 'unknown'):
            if fallback in name2id:
                return name2id[fallback]
    next_id = max(id2name.keys(), default=-1) + 1
    id2name[next_id] = name
    name2id[name] = next_id
    categories_out.append({'id': next_id, 'name': name})
    return next_id


def predictions_to_coco_annotations(image_id, predictions, name2id, id2name, categories_out):
    anns = []
    for pred in predictions or []:
        bbox = pred.get('bbox')
        if not bbox:
            continue
        name = pred.get('name') or '未知'
        cat_id = resolve_category_id(name, name2id, id2name, categories_out)
        w, h = bbox[2], bbox[3]
        anns.append({
            'image_id': image_id,
            'category_id': cat_id,
            'bbox': bbox,
            'area': w * h,
            'score': pred.get('confidence', 0),
            'category': name,
            'defect_type': pred.get('defect_type'),
            'source': pred.get('source'),
        })
    return anns


def row_to_coco_image(idx, row, img_path=None):
    """构建 COCO images 条目（不含 annotations）。"""
    from studio.query.row_fields import normalize_result_row_fields  # noqa: WPS433 — 避免循环 import 在模块级

    path = img_path
    if path is None:
        path = row.get('img_path')
    if pd.isna(path):
        path = ''
    import os
    file_name = os.path.basename(str(path)) if path else ''

    norm = normalize_result_row_fields(row)
    info = {
        'id': int(idx),
        'file_name': file_name,
        'position': norm.get('position') or row.get('position'),
        'product_id': norm.get('product_id') or '',
        'product_no': norm.get('product_no') or '',
        'product_type': norm.get('product_type') or '',
        'SN': norm.get('product_no') or '',
        'c_time': row.get('c_time'),
        'check_status': row.get('check_status'),
        'detection_result_status': row.get('detection_result_status'),
        'manual_check_status': row.get('manual_check_status'),
    }
    return {k: v for k, v in info.items() if v is not None and v != '' and not (isinstance(v, float) and pd.isna(v))}
