"""历史回跑评测：从 predict_result 选 job + 规则 → 建 replay_eval 筛选批次。"""
from __future__ import annotations

import json

import pandas as pd

from studio.curation import curation_service
from studio.curation.dispositions import (
    DISP_FN_MISSED,
    DISP_NG_CONFIRMED,
    INTENT_REPLAY_EVAL,
)
from studio.forge import forge_db


def parse_replay_filters(body=None):
    """解析向导筛选参数 → forge_db predict_result filters。"""
    body = body or {}
    mode = str(body.get('filter_mode') or body.get('mode') or 'ng_only').strip().lower()
    filters = {'sort': body.get('sort') or 'score_desc'}

    if mode in ('ng_only', 'ng', 'detected'):
        filters['only_with_boxes'] = True
    elif mode in ('clean_only', 'clean', 'no_box', 'fn'):
        filters['zero_boxes_only'] = True
    elif mode == 'all':
        pass
    else:
        filters['only_with_boxes'] = True

    if body.get('ng_only') and mode == 'all':
        filters['only_with_boxes'] = True
    if body.get('min_box_count') is not None and str(body.get('min_box_count')).strip() != '':
        filters['min_box_count'] = int(body['min_box_count'])
    if body.get('min_max_score') is not None and str(body.get('min_max_score')).strip() != '':
        filters['min_max_score'] = float(body['min_max_score'])
    if body.get('max_max_score') is not None and str(body.get('max_max_score')).strip() != '':
        filters['max_max_score'] = float(body['max_max_score'])
    if body.get('product_no'):
        filters['product_no'] = str(body['product_no']).strip()
    if body.get('product_type'):
        filters['product_type'] = str(body['product_type']).strip()
    if body.get('q'):
        filters['q'] = str(body['q']).strip()
    return filters, mode


def _job_model_name(job):
    params = job.get('params') if isinstance(job.get('params'), dict) else {}
    if params.get('model_name'):
        return str(params['model_name'])
    name = str(job.get('name') or '')
    if ' · ' in name:
        return name.split(' · ', 1)[1].strip()
    return name or f'job-{job.get("id")}'


def _rows_to_dataframe(rows):
    records = []
    for r in rows:
        ext = r.get('ext')
        if isinstance(ext, dict):
            ext_str = json.dumps(ext, ensure_ascii=False)
        else:
            ext_str = ext or ''
        box_count = int(r.get('box_count') or 0)
        records.append({
            'img_path': r.get('img_path') or '',
            'product_no': r.get('product_no') or '',
            'product_type': r.get('product_type') or '',
            'product_id': r.get('product_id') or '',
            'position': r.get('position') or '',
            'check_status': '1' if box_count > 0 else '0',
            'box_count': box_count,
            'max_score': r.get('max_score'),
            'threshold': r.get('threshold'),
            'ext': ext_str,
            'id': r.get('id'),
            'job_id': r.get('job_id'),
            'model_name': r.get('model_name') or '',
        })
    return pd.DataFrame(records)


def _sample_row(r):
    return {
        'id': r.get('id'),
        'img_path': r.get('img_path'),
        'product_no': r.get('product_no'),
        'product_type': r.get('product_type'),
        'box_count': r.get('box_count'),
        'max_score': r.get('max_score'),
    }


def preview(job_id, body=None, sample_limit=8):
    """预览匹配数量与样例。"""
    job = forge_db.get_job(job_id)
    if not job:
        raise ValueError('预测作业不存在')
    if job.get('job_type') != 'predict':
        raise ValueError('仅支持 predict 类型作业')

    filters, mode = parse_replay_filters(body)
    total_all = forge_db.count_predict_results(job_id)
    total = forge_db.count_predict_results(job_id, filters=filters)
    sample = forge_db.list_predict_results(job_id, limit=sample_limit, filters=filters)
    ng_count = forge_db.count_predict_results(job_id, filters={'only_with_boxes': True})
    clean_count = forge_db.count_predict_results(job_id, filters={'zero_boxes_only': True})

    return {
        'job_id': int(job_id),
        'job': {
            'id': job['id'],
            'name': job.get('name'),
            'status': job.get('status'),
            'done': job.get('done'),
            'total': job.get('total'),
            'model_name': _job_model_name(job),
        },
        'filter_mode': mode,
        'filters': filters,
        'counts': {
            'total_all': total_all,
            'matched': total,
            'ng_boxes': ng_count,
            'zero_boxes': clean_count,
        },
        'sample': [_sample_row(r) for r in sample],
    }


def create_replay_batch(job_id, body=None, reviewer=None, note=None, limit=50000):
    """从 predict_result 建 query task + replay_eval 筛选批次。"""
    from flask import current_app
    from server.core import build_query_task

    if not forge_db.schema_ready():
        raise RuntimeError('detforge 写库未初始化，请先建表')

    job = forge_db.get_job(job_id)
    if not job:
        raise ValueError('预测作业不存在')
    if job.get('job_type') != 'predict':
        raise ValueError('仅支持 predict 类型作业')
    if job.get('status') not in ('done', 'running', 'paused', 'failed'):
        pass  # allow done mainly; still permit partial

    filters, mode = parse_replay_filters(body)
    cap = int((body or {}).get('limit') or limit)
    rows = forge_db.list_predict_results(job_id, limit=cap, filters=filters)
    if not rows:
        raise ValueError('当前筛选条件下无样本，请调整规则或确认预测作业已有结果')

    df = _rows_to_dataframe(rows)
    model_name = _job_model_name(job)
    query_meta = {
        'data_source': 'predict_result',
        'predict_job_id': int(job_id),
        'model_name': model_name,
        'intent_type': INTENT_REPLAY_EVAL,
        'replay_filter_mode': mode,
        'replay_filters': filters,
        'strategy_id': f'replay_job_{job_id}',
        'strategy_name': f'回跑 #{job_id} · {model_name}',
    }

    with current_app.app_context():
        _, task_id = build_query_task(df, query_meta)
        batch = curation_service.create_from_task(
            task_id,
            strategy_id=query_meta['strategy_id'],
            strategy_name=query_meta['strategy_name'],
            data_source='predict_result',
            intent_type=INTENT_REPLAY_EVAL,
            reviewer=reviewer,
            note=note or f'历史回跑 job #{job_id} mode={mode}',
        )

    _apply_replay_dispositions(batch['id'], mode)

    return {
        'task_id': task_id,
        'batch': forge_db.get_curation_batch(batch['id']),
        'matched_count': len(rows),
        'filter_mode': mode,
        'filters': filters,
    }


def _apply_replay_dispositions(batch_id, mode):
    """回跑批次初始 disposition：有框→确认NG，无框→漏检候选。"""
    items = forge_db.list_curation_items(batch_id, limit=100000)
    for it in items:
        meta = it.get('source_meta') if isinstance(it.get('source_meta'), dict) else {}
        row_index = meta.get('row_index')
        # 从 check_status 推断（create_from_task 已写入）
        has_ng = str(it.get('check_status') or '') in ('1', 'true', 'True')
        if mode == 'clean_only':
            disp, nl = DISP_FN_MISSED, True
        elif has_ng:
            disp, nl = DISP_NG_CONFIRMED, False
        else:
            disp, nl = DISP_FN_MISSED, True
        forge_db.update_curation_item_decision(
            batch_id, it['batch_row_id'], it.get('decision') or 'pending',
            disposition=disp, need_platform_label=nl,
        )
