"""DefectLoop ↔ COCOVisualizer 会话桥接。"""
from __future__ import annotations

import os
import threading
import time
import uuid

from studio.paths import PROJECT_ROOT

_sessions = {}
_lock = threading.Lock()
SESSION_TTL = 3600 * 4


def _purge_expired():
    now = time.time()
    with _lock:
        dead = [k for k, v in _sessions.items() if now - v.get('created_at', now) > SESSION_TTL]
        for k in dead:
            _sessions.pop(k, None)


def _task_export_dir(task_id):
    return os.path.join(PROJECT_ROOT, 'exports', str(task_id))


def _resolve_viz_coco_and_image_dir(export_dir, *, selected_indices=None):
    """查询/预测导出目录：COCO→.coco/（file_name 为原图绝对路径），供 ensure_viz_dataset 映射。"""
    from studio.export.viz_workspace import prepare_export_dir_for_viz, should_use_viz_workspace

    export_dir = os.path.abspath(export_dir)
    if should_use_viz_workspace(export_dir):
        return prepare_export_dir_for_viz(export_dir, selected_indices=selected_indices)
    coco_path = os.path.join(export_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        raise FileNotFoundError(f'COCO 文件不存在: {coco_path}')
    return coco_path, export_dir


def open_from_task(task_id, dataset_name=None, selected_indices=None):
    """从查询 task_id 打开 COCO 看图会话。"""
    task_id = str(task_id or '').strip()
    if not task_id:
        raise ValueError('task_id 必填')
    export_dir = _task_export_dir(task_id)
    if not os.path.isdir(export_dir):
        raise FileNotFoundError(f'导出目录不存在: {export_dir}')

    coco_path, image_dir = _resolve_viz_coco_and_image_dir(
        export_dir, selected_indices=selected_indices,
    )

    from server.viz_mount import get_coco_dataset_service
    svc = get_coco_dataset_service()
    name = dataset_name or f'query-{task_id}'
    stable_id = f'query-{task_id}'
    payload = svc.ensure_viz_dataset(coco_path, image_dir, name, dataset_id=stable_id)

    if selected_indices is not None:
        indices = set(int(i) for i in selected_indices)
        payload = _filter_payload_by_indices(payload, indices)

    return _store_session(payload, source='query_task', task_id=task_id)


def open_from_paths(coco_json_path, image_dir=None, dataset_name='dataset'):
    """从绝对路径打开看图（需落在允许目录内）。"""
    from studio.forge import forge_paths
    coco_json_path = os.path.abspath(coco_json_path)
    if not os.path.isfile(coco_json_path) and not os.path.isdir(coco_json_path):
        raise FileNotFoundError(f'路径不存在: {coco_json_path}')
    if not forge_paths.safe_read_path(coco_json_path):
        raise ValueError('COCO 路径不在允许范围内')
    if image_dir:
        image_dir = os.path.abspath(image_dir)
        if not forge_paths.safe_read_path(image_dir) and not os.path.isdir(image_dir):
            raise ValueError('图片目录不在允许范围内')
    else:
        image_dir = os.path.dirname(coco_json_path)

    root_dir = image_dir if os.path.isdir(image_dir) else os.path.dirname(coco_json_path)
    from studio.export.viz_workspace import should_use_viz_workspace

    if should_use_viz_workspace(root_dir):
        from studio.export.viz_workspace import prepare_export_dir_for_viz
        coco_json_path, image_dir = prepare_export_dir_for_viz(root_dir)
        from server.viz_mount import get_coco_dataset_service
        payload = get_coco_dataset_service().ensure_viz_dataset(
            coco_json_path, image_dir, dataset_name,
        )
    else:
        from server.viz_mount import get_coco_dataset_service
        payload = get_coco_dataset_service().load_single(
            coco_json_path, image_dir, dataset_name,
        )
    return _store_session(payload, source='path', coco_json_path=coco_json_path)


def _filter_payload_by_indices(payload, indices):
    """按 COCO image.id 过滤 payload（用于选中子集）。"""
    if not indices:
        return payload
    out = dict(payload)
    stats = out.get('stats') or {}
    if isinstance(stats, dict) and 'images' in stats:
        imgs = stats.get('images') or []
        stats = dict(stats)
        stats['images'] = [im for im in imgs if im.get('id') in indices or im.get('image_id') in indices]
        out['stats'] = stats
    out['selected_indices'] = sorted(indices)
    return out


def _store_session(payload, **meta):
    _purge_expired()
    session_id = f'vs_{uuid.uuid4().hex[:12]}'
    record = {
        'session_id': session_id,
        'dataset_id': payload.get('dataset_id'),
        'payload': payload,
        'created_at': time.time(),
        **meta,
    }
    with _lock:
        _sessions[session_id] = record
    return {
        'session_id': session_id,
        'dataset_id': payload.get('dataset_id'),
        'dataset_name': payload.get('dataset_name'),
        'viewer_url': f'/viewer?session={session_id}',
        'viz_url': f'/viz/?defectloop_session={session_id}',
    }


def get_session(session_id):
    _purge_expired()
    with _lock:
        rec = _sessions.get(str(session_id or '').strip())
    if not rec:
        return None
    return rec
