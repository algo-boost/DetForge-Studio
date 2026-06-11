"""通用工具集成 API — GET /api/tools/<tool_id>/integration。"""
from __future__ import annotations

from flask import Blueprint, jsonify

from server.tool_integration import build_integration_payload, integration_extra_for

tool_integration_bp = Blueprint('tool_integration', __name__)


@tool_integration_bp.route('/api/tools/<tool_id>/integration', methods=['GET'])
def tool_integration_status(tool_id):
    tid = str(tool_id or '').strip().lower()
    return jsonify(build_integration_payload(tid, extra=integration_extra_for(tid)))
