"""演示用 Capability（无需数据库，用于体验 Script → Flow 编排）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone


def run_demo_query(params, context):
    keyword = str(params.get('keyword') or 'demo').strip()
    task_id = f"demo-task-{uuid.uuid4().hex[:8]}"
    rows = [
        {'sn': f'SN-{1000 + i}', 'ng_type': 'scratch', 'score': round(0.92 - i * 0.01, 3)}
        for i in range(5)
    ]
    return {
        'task_id': task_id,
        'row_count': len(rows),
        'keyword': keyword,
        'sample_rows': rows[:3],
        'data_source': 'demo',
        'queried_at': datetime.now(timezone.utc).isoformat(),
    }


def run_demo_pack(params, context):
    task_id = str(params.get('task_id') or 'demo-task')
    row_count = int(params.get('row_count') or 5)
    batch_id = abs(hash(task_id)) % 90000 + 10000
    return {
        'batch_id': batch_id,
        'batch_code': f'DEMO-{batch_id}',
        'task_id': task_id,
        'items': row_count,
        'export_dir': f'/tmp/iisp-demo/{batch_id}',
    }


def run_demo_notify(params, context):
    event = str(params.get('event') or 'demo_done')
    batch_id = params.get('batch_id')
    message = f'[IISP Demo] {event} · batch={batch_id}'
    print(message, flush=True)
    return {
        'event': event,
        'message': message,
        'batch_id': batch_id,
        'channels': ['stdout'],
    }
