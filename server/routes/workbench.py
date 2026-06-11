"""L1 工作台 API。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from server.services import workbench as wb

workbench_bp = Blueprint('workbench', __name__, url_prefix='/api/workbench')


@workbench_bp.route('/todos', methods=['GET'])
def workbench_todos():
    limit = int(request.args.get('limit') or 50)
    return jsonify({'success': True, 'data': wb.list_todos(limit=limit)})


@workbench_bp.route('/summary', methods=['GET'])
def workbench_summary():
    return jsonify({'success': True, 'data': wb.build_summary()})


@workbench_bp.route('/flows/runs', methods=['GET'])
def workbench_flow_runs():
    status = (request.args.get('status') or '').strip() or None
    limit = int(request.args.get('limit') or 20)
    rows: list[dict] = []
    if status in (None, 'waiting_human'):
        for r in wb.collect_kestra_paused(limit=limit):
            rows.append({
                'run_id': r['execution_id'],
                'flow_id': r.get('flow_id'),
                'status': 'waiting_human',
                'source': 'kestra',
                'batch_id': r.get('batch_id'),
                'kestra_url': r.get('kestra_url'),
            })
    rows.extend(wb.collect_demo_flow_runs(status=status)[:limit])
    return jsonify({'success': True, 'data': rows[:limit]})


@workbench_bp.route('/flows/list', methods=['GET'])
def workbench_flow_list():
    from orchestration.loader import discover_kestra_flows

    return jsonify({'success': True, 'data': discover_kestra_flows()})
