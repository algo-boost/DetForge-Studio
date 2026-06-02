"""查询 vision_backend 部署/训练模型及路径信息（本地总控，非 Magic-Fox 线上）。"""
import json
import os

from studio.query.approach_context import resolve_local_approach_id
from studio.query.defect_categories import DETECTION_TRAIN_TYPES, is_detection_model_type
from studio.query.platform_paths import build_deploy_full_path, resolve_platform_paths


def _labels_from_extra(extra_result):
    if not extra_result:
        return []
    try:
        data = json.loads(extra_result) if isinstance(extra_result, str) else extra_result
    except (json.JSONDecodeError, TypeError):
        return []
    labels = data.get('labels') or data.get('label_names') or []
    if isinstance(labels, dict):
        return [str(k).strip() for k in labels.keys() if str(k).strip()]
    if isinstance(labels, list):
        return [str(x).strip() for x in labels if str(x).strip()]
    tc = data.get('train_config') or {}
    if isinstance(tc, str):
        try:
            tc = json.loads(tc)
        except (json.JSONDecodeError, TypeError):
            tc = {}
    if isinstance(tc, dict):
        ml = tc.get('model_labels')
        parsed = _labels_from_model_labels(ml)
        if parsed:
            return parsed
    return []


def fetch_deployed_models(client, config=None, approach_id=None, limit=30, drive=None):
    """
    返回在线部署模型列表，含可拼接的完整权重路径。
    完整路径 = {platform_root}/resources/backend/local_file/{object_key}
    """
    config = dict(config or {})
    if drive:
        config = {**config, 'platform_root_drive': drive}

    paths = resolve_platform_paths(client, config)
    local_file_base = paths.get('local_file_base', '')
    aid = resolve_local_approach_id(config, override=approach_id)
    limit = max(1, min(int(limit or 30), 100))

    rows = []
    meta = {
        'approach_id': aid,
        'platform_root': paths.get('platform_root', ''),
        'local_file_base': local_file_base,
        'platform_root_drive': paths.get('platform_root_drive', ''),
        'source': 'modeldeploy',
    }

    if client is None or client.connection is None:
        meta['error'] = '数据库未连接'
        return {'models': rows, 'meta': meta}

    try:
        df = client.query(f"""
            SELECT
                id,
                deploy_name,
                object_key,
                approach_id,
                extra_result,
                c_time,
                JSON_UNQUOTE(JSON_EXTRACT(extra_result, '$.model_type')) AS model_type
            FROM modeldeploy
            WHERE approach_id = {aid}
              AND object_key IS NOT NULL AND object_key != ''
            ORDER BY id DESC
            LIMIT {limit}
        """)
    except Exception as e:
        meta['error'] = str(e)
        return {'models': rows, 'meta': meta}

    if df is None or df.empty:
        return {'models': rows, 'meta': meta}

    for _, row in df.iterrows():
        object_key = str(row.get('object_key') or '').strip()
        full_path = build_deploy_full_path(local_file_base, object_key)
        if full_path:
            full_path = full_path.replace('/', '\\')
        rows.append({
            'id': int(row.get('id') or 0),
            'deploy_name': str(row.get('deploy_name') or '').strip(),
            'object_key': object_key,
            'model_type': str(row.get('model_type') or '').strip(),
            'approach_id': int(row.get('approach_id') or aid),
            'full_path': full_path,
            'path_resolvable': bool(full_path),
            'labels': _labels_from_extra(row.get('extra_result')),
            'c_time': str(row.get('c_time') or ''),
        })

    return {'models': rows, 'meta': meta}


def _labels_from_model_labels(raw):
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if str(x).strip()]
    try:
        obj = json.loads(raw) if isinstance(raw, str) else raw
        if isinstance(obj, list):
            return [str(x).strip() for x in obj if str(x).strip()]
        if isinstance(obj, dict):
            # Magic-Fox：{"脏污": "rgba(...)"} → 取类别名（key）
            return [str(k).strip() for k in obj.keys() if str(k).strip()]
    except (json.JSONDecodeError, TypeError):
        pass
    return []


def fetch_training_models(client, config=None, approach_id=None, limit=30):
    """
    查询 modeltrainconfig 训练配置。
    model_store_key 仅为相对路径（如 ckpts/...），库内无法拼出可靠绝对路径。
    """
    config = dict(config or {})
    aid = resolve_local_approach_id(config, override=approach_id)
    limit = max(1, min(int(limit or 30), 100))
    paths = resolve_platform_paths(client, config)
    platform_root = paths.get('platform_root', '')

    rows = []
    meta = {
        'approach_id': aid,
        'platform_root': platform_root,
        'source': 'modeltrainconfig',
        'path_note': (
            'model_store_key 为相对路径；完整 ckpt 需结合训练任务输出目录手动定位，'
            '无法像 modeldeploy.object_key 一样仅从库记录拼出绝对路径。'
        ),
    }

    if client is None or client.connection is None:
        meta['error'] = '数据库未连接'
        return {'models': rows, 'meta': meta}

    det_types = "', '".join(sorted(DETECTION_TRAIN_TYPES))
    try:
        df = client.query(f"""
            SELECT
                id,
                model_name,
                model_type,
                model_store_key,
                model_labels,
                c_time
            FROM modeltrainconfig
            WHERE approach_id = {aid}
              AND model_type IN ('{det_types}')
            ORDER BY id DESC
            LIMIT {limit}
        """)
    except Exception as e:
        meta['error'] = str(e)
        return {'models': rows, 'meta': meta}

    if df is None or df.empty:
        return {'models': rows, 'meta': meta}

    for _, row in df.iterrows():
        store_key = str(row.get('model_store_key') or '').strip()
        model_type = str(row.get('model_type') or '').strip()
        full_path = ''
        if platform_root and store_key:
            full_path = f'{platform_root}\\{store_key.replace("/", chr(92))}'
        path_resolvable = bool(full_path and os.path.isfile(full_path))
        rows.append({
            'id': int(row.get('id') or 0),
            'model_name': str(row.get('model_name') or '').strip(),
            'model_type': model_type,
            'model_store_key': store_key,
            'hint_path': full_path,
            'full_path': full_path,
            'path_resolvable': path_resolvable,
            'labels': _labels_from_model_labels(row.get('model_labels')),
            'c_time': str(row.get('c_time') or ''),
            'is_detection': is_detection_model_type(model_type),
            'approach_id': aid,
        })

    return {'models': rows, 'meta': meta}
