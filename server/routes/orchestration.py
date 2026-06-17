"""编排 Resume API（workflow / demo）。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.services.flows import resume_flow_run

orchestration_bp = Blueprint('orchestration', __name__, url_prefix='/v1/orchestration')


@orchestration_bp.route('/executions/paused', methods=['GET'])
def list_paused():
    from server.services import workbench as wb

    limit = int(request.args.get('limit') or 20)
    rows = []
    for run in wb.collect_workflow_runs(status='waiting_human', limit=limit):
        rows.append({
            'execution_id': str(run.get('id')),
            'flow_id': run.get('template_id'),
            'source': 'workflow',
            'started_at': run.get('created_at'),
        })
    for row in wb.collect_demo_flow_runs(status='waiting_human')[:limit]:
        rows.append({
            'execution_id': row['run_id'],
            'flow_id': row.get('flow_id'),
            'source': 'demo',
        })
    return jsonify({'success': True, 'data': rows})


@orchestration_bp.route('/resume', methods=['POST'])
def resume():
    body = request.get_json(silent=True) or {}
    run_key = str(body.get('run_key') or '').strip()
    execution_id = str(body.get('execution_id') or '').strip()
    if not run_key and execution_id:
        source = str(body.get('source') or 'workflow')
        run_key = f'{source}:{execution_id}'
    if not run_key:
        return jsonify({'success': False, 'error': '缺少 run_key 或 execution_id'}), 400
    try:
        data = resume_flow_run(run_key, body)
        return jsonify({'success': True, 'data': data})
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 400
