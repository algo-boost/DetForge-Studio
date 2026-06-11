"""Tool Contract v1 Gateway（Kestra 编排入口）。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from capabilities.base import RunContext
from server.gateway.contract import failed_v1, result_to_v1

gateway_bp = Blueprint('gateway', __name__, url_prefix='/v1')


@gateway_bp.route('/tools', methods=['GET'])
def list_tools_v1():
    from capabilities.registry import get_registry

    reg = get_registry()
    tools = []
    for item in reg.list_tools():
        tools.append({
            'id': item['id'],
            'label': item.get('label'),
            'description': item.get('description'),
            'kind': item.get('kind'),
            'version': item.get('version'),
            'invoke': f"/v1/tools/{item['id']}/invoke",
            'params_schema': item.get('params_schema'),
            'outputs': item.get('outputs'),
        })
    return jsonify({'tools': tools})


@gateway_bp.route('/tools/<tool_id>/invoke', methods=['POST'])
def invoke_tool_v1(tool_id):
    from capabilities.registry import get_registry

    body = request.get_json(silent=True) or {}
    reg = get_registry()
    ctx = RunContext(
        run_id=body.get('run_id'),
        step_id=body.get('step_id'),
        params=body.get('params') or {},
        inputs=body.get('inputs') or {},
    )
    try:
        result = reg.execute(tool_id, ctx)
    except ValueError as exc:
        return jsonify(failed_v1(str(exc))), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify(failed_v1(str(exc))), 500
    return jsonify(result_to_v1(result))
