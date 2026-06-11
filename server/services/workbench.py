"""工作台待办与摘要聚合。"""
from __future__ import annotations

from datetime import datetime, timezone

CURATION_STATUS_LABEL = {
    'created': '待出站',
    'exported': '待回传 COCO',
    'imported': '待归档',
    'archived': '待交接',
    'handoff_ready': '交接就绪',
}


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def _workflow_todo(run: dict) -> dict:
    run_id = run.get('id')
    template_id = run.get('template_id') or '工作流'
    return {
        'id': f'workflow-{run_id}',
        'kind': 'workflow_human_gate',
        'title': f'{template_id} · 待人工处理',
        'subtitle': f'Run #{run_id}',
        'status': 'waiting_human',
        'href': f'/flows/runs/workflow:{run_id}',
        'created_at': _iso(run.get('created_at') or run.get('started_at')),
        'meta': {'run_id': run_id, 'template_id': template_id},
    }


def _demo_flow_todo(run_id: str, pending: dict) -> dict:
    defn = pending.get('defn') or {}
    flow_id = defn.get('id') or 'demo_flow'
    return {
        'id': f'demo-flow-{run_id}',
        'kind': 'flow_human_gate',
        'title': f'{defn.get("name") or flow_id} · 演示 Flow',
        'subtitle': f'暂停于 {pending.get("pause_at")}',
        'status': 'waiting_human',
        'href': f'/flows/runs/demo:{run_id}',
        'created_at': None,
        'meta': {'run_id': run_id, 'flow_id': flow_id, 'pause_at': pending.get('pause_at')},
    }


def _kestra_todo(row: dict) -> dict:
    flow_id = row.get('flow_id') or 'flow'
    batch_id = row.get('batch_id')
    href = row.get('ui_url') or f"/flows/runs/kestra:{row.get('execution_id')}"
    subtitle = f"execution {row.get('execution_id')}"
    if batch_id:
        subtitle = f'batch {batch_id}'
    return {
        'id': f"kestra-{row.get('execution_id')}",
        'kind': 'kestra_pause',
        'title': f'{flow_id} · Kestra 待人工',
        'subtitle': subtitle,
        'status': 'waiting_human',
        'href': href,
        'created_at': row.get('started_at'),
        'meta': row,
    }


def _manual_qc_todo(group: dict) -> dict:
    batch_id = group.get('batch_id') or group.get('batch_key') or '—'
    intake = int(group.get('intake_count') or 0)
    confirmed = int(group.get('confirmed_count') or 0)
    parts = []
    if intake:
        parts.append(f'待核对 {intake}')
    if confirmed:
        parts.append(f'待确认 {confirmed}')
    subtitle = ' · '.join(parts) or f"{int(group.get('total') or 0)} 条"
    return {
        'id': f'mqc-{batch_id}',
        'kind': 'manual_qc',
        'title': f'人工质检 · {batch_id}',
        'subtitle': subtitle,
        'status': 'pending',
        'href': '/manual-qc',
        'created_at': _iso(group.get('first_at')),
        'meta': {
            'batch_id': batch_id,
            'intake_count': intake,
            'confirmed_count': confirmed,
            'total': int(group.get('total') or 0),
        },
    }


def _curation_todo(batch: dict) -> dict:
    bid = batch.get('id')
    status = str(batch.get('status') or 'created')
    label = CURATION_STATUS_LABEL.get(status, status)
    code = batch.get('batch_code') or f'批次 #{bid}'
    intent = batch.get('intent_type') or batch.get('intent_label')
    strategy = batch.get('strategy_name')
    subtitle = strategy or intent
    if batch.get('pending_count'):
        subtitle = f"{subtitle or ''} · 待筛 {batch['pending_count']}".strip(' ·')
    return {
        'id': f'curation-{bid}',
        'kind': 'curation_batch',
        'title': f'{code} · {label}',
        'subtitle': subtitle or None,
        'status': 'pending',
        'href': f'/curation?id={bid}',
        'created_at': _iso(batch.get('created_at')),
        'meta': {'batch_id': bid, 'status': status, 'batch_code': code},
    }


def collect_workflow_runs(*, status: str | None = None, limit: int = 50) -> list[dict]:
    try:
        from studio.forge import forge_db

        if not forge_db.schema_ready():
            return []
        return forge_db.list_workflow_runs(status=status, limit=limit)
    except Exception:
        return []


def collect_demo_flow_runs(*, status: str | None = None) -> list[dict]:
    from server.routes.tools import _demo_flow_runs

    rows = []
    for run_id, pending in _demo_flow_runs.items():
        steps = pending.get('steps') or []
        last_status = steps[-1].get('status') if steps else 'waiting_human'
        row_status = 'waiting_human' if pending.get('pause_at') else last_status
        row = {
            'run_id': run_id,
            'flow_id': (pending.get('defn') or {}).get('id'),
            'status': row_status,
            'pause_at': pending.get('pause_at'),
            'steps': steps,
            '_pending': pending,
        }
        if status and row['status'] != status:
            continue
        rows.append(row)
    return rows


def collect_kestra_paused(*, limit: int = 20) -> list[dict]:
    if not _kestra_enabled():
        return []
    try:
        from orchestration import kestra_client as kc

        return [kc.summarize_paused(ex) for ex in kc.list_paused_executions(limit=limit)]
    except Exception:
        return []


def collect_manual_qc_pending(*, limit: int = 20) -> list[dict]:
    try:
        from studio.forge import forge_db

        if not forge_db.schema_ready():
            return []
        return forge_db.list_manual_qc_pending_groups(limit=limit)
    except Exception:
        return []


def collect_curation_pending(*, limit: int = 20) -> list[dict]:
    try:
        from studio.forge import forge_db

        if not forge_db.schema_ready():
            return []
        return forge_db.list_curation_action_batches(limit=limit)
    except Exception:
        return []


def _kestra_enabled() -> bool:
    try:
        from orchestration import kestra_client as kc
        return kc.is_enabled()
    except Exception:
        return False


def _sort_todos(todos: list[dict]) -> list[dict]:
    return sorted(
        todos,
        key=lambda t: t.get('created_at') or '',
        reverse=True,
    )


def list_todos(limit: int = 50) -> list[dict]:
    per_source = max(limit, 20)
    todos: list[dict] = []
    for run in collect_workflow_runs(status='waiting_human', limit=per_source):
        todos.append(_workflow_todo(run))
    for row in collect_demo_flow_runs(status='waiting_human'):
        todos.append(_demo_flow_todo(row['run_id'], row['_pending']))
    for row in collect_kestra_paused(limit=per_source):
        todos.append(_kestra_todo(row))
    for group in collect_manual_qc_pending(limit=per_source):
        todos.append(_manual_qc_todo(group))
    for batch in collect_curation_pending(limit=per_source):
        todos.append(_curation_todo(batch))
    return _sort_todos(todos)[:limit]


def build_summary() -> dict:
    waiting = collect_workflow_runs(status='waiting_human', limit=200)
    demo_waiting = collect_demo_flow_runs(status='waiting_human')
    kestra_waiting = collect_kestra_paused(limit=200)
    mqc_pending = collect_manual_qc_pending(limit=200)
    curation_pending = collect_curation_pending(limit=200)
    running = collect_workflow_runs(status='running', limit=200)
    active_queries = 0
    try:
        from studio.query.query_jobs import list_query_jobs

        active_queries = len(list_query_jobs(active_only=True))
    except Exception:
        pass
    todo_count = (
        len(waiting)
        + len(demo_waiting)
        + len(kestra_waiting)
        + len(mqc_pending)
        + len(curation_pending)
    )
    return {
        'todo_count': todo_count,
        'waiting_human_count': len(waiting) + len(demo_waiting) + len(kestra_waiting),
        'manual_qc_batch_count': len(mqc_pending),
        'curation_batch_count': len(curation_pending),
        'running_flow_count': len(running),
        'active_query_count': active_queries,
        'kestra_paused_count': len(kestra_waiting),
    }
