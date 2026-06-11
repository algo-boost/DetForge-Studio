"""M2 编排冒烟用 Capability（写真实 task 目录，无需业务库查询）。"""
from __future__ import annotations

import csv
import json
import os
import uuid


def run_smoke_query(params, context):
    """创建带 result.csv + COCO 的查询 task，供 daily_ng_curation_smoke 全链路使用。"""
    from flask import current_app

    row_count = max(1, min(int(params.get('row_count') or 2), 20))
    task_id = f"smoke-{uuid.uuid4().hex[:12]}"
    task_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], task_id)
    os.makedirs(task_dir, exist_ok=True)

    rows = [
        {
            'img_name': f'smoke_{i + 1}.jpg',
            'product_no': f'PN-{1000 + i}',
            'product_type': 'demo',
            'check_status': 'ng',
        }
        for i in range(row_count)
    ]
    csv_path = os.path.join(task_dir, 'result.csv')
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    query_meta = {
        'strategy_id': params.get('strategy_id') or 'smoke',
        'strategy_name': params.get('strategy_name') or 'M2 冒烟',
        'data_source': 'smoke',
    }
    with open(os.path.join(task_dir, 'query_meta.json'), 'w', encoding='utf-8') as f:
        json.dump(query_meta, f, ensure_ascii=False, indent=2)

    coco = {
        'info': {'description': 'IISP M2 smoke fixture'},
        'images': [
            {'id': i + 1, 'file_name': rows[i]['img_name'], 'width': 640, 'height': 480}
            for i in range(row_count)
        ],
        'annotations': [],
        'categories': [{'id': 1, 'name': 'defect'}],
    }
    with open(os.path.join(task_dir, '_annotations.coco.json'), 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)

    return {
        'task_id': task_id,
        'row_count': row_count,
        'count': row_count,
        'data_source': 'smoke',
    }
