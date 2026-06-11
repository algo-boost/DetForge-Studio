"""编排 Resume API（Kestra Hub）。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from orchestration import kestra_client as kc

orchestration_bp = Blueprint('orchestration', __name__, url_prefix='/v1/orchestration')


@orchestration_bp.route('/executions/paused', methods=['GET'])
def list_paused():
    if not kc.is_enabled():
        return jsonify({'success': True, 'data': [], 'kestra_enabled': False})
    limit = int(request.args.get('limit') or 20)
    namespace = (request.args.get('namespace') or '').strip() or None
    try:
        rows = [kc.summarize_paused(ex) for ex in kc.list_paused_executions(limit=limit, namespace=namespace)]
        return jsonify({'success': True, 'data': rows, 'kestra_enabled': True})
    except kc.KestraError as exc:
        return jsonify({'success': False, 'error': str(exc), 'kestra_enabled': True}), exc.status_code or 502


@orchestration_bp.route('/executions/<execution_id>', methods=['GET'])
def get_execution(execution_id: str):
    if not kc.is_enabled():
        return jsonify({'success': False, 'error': 'Kestra 未启用'}), 503
    try:
        ex = kc.get_execution(execution_id)
        return jsonify({'success': True, 'data': kc.summarize_paused(ex) if _is_paused(ex) else ex})
    except kc.KestraError as exc:
        return jsonify({'success': False, 'error': str(exc)}), exc.status_code or 502


@orchestration_bp.route('/resume', methods=['POST'])
def resume():
    if not kc.is_enabled():
        return jsonify({'success': False, 'error': 'Kestra 未启用'}), 503
    body = request.get_json(silent=True) or {}
    execution_id = str(body.get('execution_id') or '').strip()
    if not execution_id:
        return jsonify({'success': False, 'error': '缺少 execution_id'}), 400
    inputs = body.get('inputs') if isinstance(body.get('inputs'), dict) else None
    try:
        data = kc.resume_execution(execution_id, inputs=inputs)
        return jsonify({'success': True, 'data': data})
    except kc.KestraError as exc:
        code = exc.status_code or 502
        if code == 409:
            return jsonify({'success': False, 'error': '执行未处于 PAUSED 状态'}), 409
        return jsonify({'success': False, 'error': str(exc)}), code


def _is_paused(execution: dict) -> bool:
    return ((execution or {}).get('state') or {}).get('current') == 'PAUSED'
