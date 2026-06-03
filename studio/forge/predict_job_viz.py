"""预测作业结果 → COCO 导出与样本图库打开。"""
from __future__ import annotations

import os

from studio.paths import PROJECT_ROOT


def _predict_result_filters(kwargs):
    from studio.forge.predict_result_filters import normalize_filter_dict

    keys = (
        'min_box_count', 'min_max_score', 'max_max_score', 'only_with_boxes', 'zero_boxes_only',
        'q', 'product_no', 'product_type', 'sort', 'categories',
        'min_pred_confidence', 'max_pred_confidence',
    )
    out = {}
    for k in keys:
        v = (kwargs or {}).get(k)
        if v is not None and v != '':
            out[k] = v
    return normalize_filter_dict(out)


def _resolve_model_name(job, rows):
    params = (job or {}).get('params') or {}
    for candidate in (
        params.get('model_name'),
        (rows[0].get('model_name') if rows else None),
        job.get('name') if job else None,
        f'job{(job or {}).get("id")}',
    ):
        if candidate and str(candidate).strip():
            return str(candidate).strip()
    return 'predict'


def export_predict_job_coco(job_id, filters=None, result_ids=None):
    """将 predict_result 导出为 GT 主 COCO + pred 侧车，返回 (export_dir, coco_path, image_count)。"""
    from studio.forge import forge_db
    from studio.export.pred_coco_layout import build_predict_view_coco

    job = forge_db.get_job(job_id)
    if not job:
        raise ValueError(f'作业不存在: {job_id}')

    f = _predict_result_filters(filters)
    rows = forge_db.list_predict_results(
        job_id, limit=10000, offset=0, filters=f, result_ids=result_ids,
    )
    if not rows:
        raise ValueError('没有符合条件的预测结果')

    import json

    import pandas as pd

    export_dir = os.path.join(PROJECT_ROOT, 'exports', f'predict_job_{int(job_id)}')
    os.makedirs(export_dir, exist_ok=True)
    model_name = _resolve_model_name(job, rows)

    csv_rows = []
    for row in rows:
        csv_rows.append({
            'id': row.get('id'),
            'img_path': row.get('img_path'),
            'product_no': row.get('product_no'),
            'job_id': row.get('job_id'),
        })
    pd.DataFrame(csv_rows).to_csv(
        os.path.join(export_dir, 'result.csv'), index=False, encoding='utf-8',
    )
    meta_path = os.path.join(export_dir, 'query_meta.json')
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump({
            'data_source': 'predict_result',
            'query_mode': 'predict_job',
            'job_id': int(job_id),
            'model_name': model_name,
        }, f, ensure_ascii=False, indent=2)

    gt_path, _pred_path, count, _src = build_predict_view_coco(
        rows,
        export_dir=export_dir,
        model_name=model_name,
        info_meta={
            'query_mode': 'predict_job',
            'job_id': int(job_id),
            'job_name': job.get('name'),
            'model_name': model_name,
        },
        image_id_key='id',
        merge_nearby_gt=False,
        emit_pred_sidecar=False,
    )
    return export_dir, gt_path, count


def open_predict_job_viz(job_id, filters=None, result_ids=None, dataset_name=None):
    """导出并注册 COCOVisualizer 会话。"""
    from studio import viz_bridge
    from studio.forge import forge_db

    export_dir, coco_path, _count = export_predict_job_coco(
        job_id, filters=filters, result_ids=result_ids,
    )
    job = forge_db.get_job(job_id)
    name = dataset_name or f'predict-#{job_id} · {(job or {}).get("name") or "job"}'
    return viz_bridge.open_from_paths(coco_path, image_dir=export_dir, dataset_name=name)
