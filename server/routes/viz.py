"""DefectLoop 看图桥接 API + COCOVisualizer 挂载。"""
from flask import Blueprint, request, jsonify

from server.viz_mount import register_viz_mount, is_viz_available, VIZ_MOUNT_PREFIX
from studio import viz_bridge

viz_bp = Blueprint('viz', __name__)

_viz_mounted = False


def ensure_viz_mounted(app):
    global _viz_mounted
    if not _viz_mounted:
        _viz_mounted = register_viz_mount(app)


@viz_bp.route('/api/viz/status', methods=['GET'])
def viz_status():
    return jsonify({
        'success': True,
        'available': is_viz_available(),
        'mount_prefix': VIZ_MOUNT_PREFIX,
    })


@viz_bp.route('/api/viz/open', methods=['POST'])
def viz_open():
    try:
        data = request.json or {}
        source = data.get('source') or 'query_task'
        if source == 'query_task':
            result = viz_bridge.open_from_task(
                data.get('task_id'),
                dataset_name=data.get('dataset_name'),
                selected_indices=data.get('selected_indices'),
            )
        elif source == 'path':
            result = viz_bridge.open_from_paths(
                data.get('coco_json_path'),
                image_dir=data.get('image_dir'),
                dataset_name=data.get('dataset_name') or 'dataset',
            )
        else:
            return jsonify({'success': False, 'error': f'未知 source: {source}'}), 400
        return jsonify({'success': True, **result})
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(e)}), 500


@viz_bp.route('/api/viz/session/<session_id>', methods=['GET'])
def viz_session(session_id):
    rec = viz_bridge.get_session(session_id)
    if not rec:
        return jsonify({'success': False, 'error': '会话不存在或已过期'}), 404
    return jsonify({
        'success': True,
        'session_id': rec['session_id'],
        'dataset_id': rec.get('dataset_id'),
        'source': rec.get('source'),
        'task_id': rec.get('task_id'),
        'payload': rec.get('payload'),
        'viewer_url': f'/viewer?session={rec["session_id"]}',
        'viz_url': f'{VIZ_MOUNT_PREFIX}/?defectloop_session={rec["session_id"]}',
    })
