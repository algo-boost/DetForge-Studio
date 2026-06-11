"""DefectLoop ↔ DetUnify 桥接 API + DetUnify 挂载。"""
from flask import Blueprint, jsonify

from server.unify_mount import (
    register_unify_mount,
    is_unify_available,
    is_unify_mounted,
    UNIFY_MOUNT_PREFIX,
)

unify_bp = Blueprint('unify', __name__)

_unify_mounted = False


def ensure_unify_mounted(app):
    global _unify_mounted
    if not _unify_mounted:
        _unify_mounted = register_unify_mount(app)


@unify_bp.route('/api/unify/status', methods=['GET'])
def unify_status():
    from server.tool_integration import build_integration_payload, unify_integration_extra
    return jsonify(build_integration_payload('unify', extra=unify_integration_extra()))
