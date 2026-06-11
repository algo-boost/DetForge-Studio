"""Query 工具 REST 状态与 invoke 包装（/api/query-tool/*）。"""
from __future__ import annotations

import json
from pathlib import Path

from flask import Blueprint, jsonify, request

from capabilities.base import RunContext
from capabilities.registry import get_registry
from server.gateway.contract import result_to_v1
from server.tool_integration import build_integration_payload

query_tool_bp = Blueprint('query_tool', __name__)

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / 'tools' / 'query' / 'tool.manifest.json'


def _query_extra() -> dict:
    from server.query_mount import (
        QUERY_MOUNT_PREFIX,
        is_query_tool_ui_available,
        is_query_tool_ui_mounted,
    )
    from tools.query.ui_server import is_query_tool_ui_built, resolve_query_tool_ui_root

    manifest = {}
    if _MANIFEST.is_file():
        manifest = json.loads(_MANIFEST.read_text(encoding='utf-8'))

    return {
        'version': manifest.get('version'),
        'mount_prefix': QUERY_MOUNT_PREFIX,
        'mount_available': is_query_tool_ui_available(),
        'built': is_query_tool_ui_built(),
        'mount_ready': is_query_tool_ui_mounted(),
        'available': is_query_tool_ui_available(),
        'mounted': is_query_tool_ui_mounted(),
        'ui_root': resolve_query_tool_ui_root() or None,
        'routes': (manifest.get('entry') or {}).get('ui', {}).get('routes') or [],
        'invoke': '/v1/tools/query/invoke',
        'legacy_rest': [
            '/api/query',
            '/api/query/jobs',
            '/api/query/task/<task_id>',
            '/api/strategies',
        ],
    }


@query_tool_bp.route('/api/query-tool/status', methods=['GET'])
def query_tool_status():
    return jsonify(build_integration_payload('query', extra=_query_extra()))


@query_tool_bp.route('/api/query-tool/invoke', methods=['POST'])
def query_tool_invoke():
    """Legacy 友好包装 — body.params 同 Gateway。"""
    body = request.get_json(silent=True) or {}
    reg = get_registry()
    ctx = RunContext(
        run_id=body.get('run_id'),
        step_id=body.get('step_id'),
        params=body.get('params') or {},
        inputs=body.get('inputs') or {},
    )
    try:
        result = reg.execute('query', ctx)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    v1 = result_to_v1(result)
    return jsonify({'success': result.status != 'failed', **v1})
