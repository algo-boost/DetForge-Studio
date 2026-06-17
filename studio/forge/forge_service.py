"""作业编排与模型导入的高层服务（被 routes 调用）。"""
import os

import pandas as pd

from studio.forge import forge_db

from studio.paths import PROJECT_ROOT as BASE_DIR
IMG_EXTS = ('.jpg', '.jpeg', '.png', '.bmp', '.webp')

# modeldeploy / modeltrainconfig 的 model_type → (framework, sub_type)
HQ_SUB_TYPES = ('dino', 'dino2', 'rtdetr', 'rtmdet', 'yolo', 'lwdetr', 'rfdetr', 'codetr')


def infer_framework(model_type, source=''):
    """从平台 model_type 字符串推断 (framework, sub_type)。dino 默认走 ml_backend。"""
    mt = str(model_type or '').strip().lower()
    if not mt or mt in ('null', 'none', 'undefined'):
        return '', None
    if mt == 'dino':
        return 'dino', None
    if mt in HQ_SUB_TYPES:
        return 'hq_det', mt
    # vision_backend 部署编码如 DET0307、DETRTDETR — 仅当后缀能识别子类型
    if mt.startswith('det'):
        for sub in HQ_SUB_TYPES:
            if sub in mt:
                return 'hq_det', sub
        # Magic-Fox 部署编码如 DET0307、DET0303 — 无子类型后缀时仍走 hq_det
        return 'hq_det', None


# ── 模型导入 ───────────────────────────────────────────────────────

def import_model(payload):
    """注册/导入模型到 model_registry，返回 model_id。

    payload: name, framework, sub_type, checkpoint_path, labels, source,
             source_ref, approach_id, default_params, model_type(可选,用于自动推断)。
    """
    framework = (payload.get('framework') or '').strip()
    sub_type = payload.get('sub_type')
    checkpoint_path = (payload.get('checkpoint_path') or '').strip()
    if not checkpoint_path:
        raise ValueError('checkpoint_path 不能为空')
    if not framework and payload.get('model_type'):
        framework, sub_type = infer_framework(payload.get('model_type'), payload.get('source'))
    if not framework and os.path.isfile(checkpoint_path):
        from studio.forge import predict_runtime
        from server.core import load_config
        fw, st = predict_runtime.detect_model_framework(
            checkpoint_path, config=payload.get('_config') or load_config(),
        )
        if fw:
            framework, sub_type = fw, st or sub_type
    if not framework:
        raise ValueError('无法确定 framework（dino|hq_det），请显式选择或在设置中配置 predict_python_executable')

    default_params = payload.get('default_params') or {}
    for key, default in (('threshold', 0.5), ('max_size', 1536), ('device', 'cuda:0')):
        default_params.setdefault(key, default)

    return forge_db.upsert_model({
        'name': payload.get('name') or os.path.basename(checkpoint_path),
        'framework': framework,
        'sub_type': sub_type,
        'checkpoint_path': checkpoint_path,
        'labels': payload.get('labels'),
        'source': payload.get('source') or 'manual',
        'source_ref': payload.get('source_ref'),
        'approach_id': payload.get('approach_id'),
        'default_params': default_params,
        'enabled': payload.get('enabled', 1),
    })


# ── 预测作业编排 ───────────────────────────────────────────────────

def _items_from_task(task_id, selected_indices=None):
    """从 exports/<task_id>/result.csv 读取图片与产品字段。"""
    csv_path = os.path.join(BASE_DIR, 'exports', task_id, 'result.csv')
    if not os.path.exists(csv_path):
        raise ValueError(f'任务结果不存在: {task_id}')
    df = pd.read_csv(csv_path, encoding='utf-8')
    sel = None
    if selected_indices is not None:
        sel = {int(i) for i in selected_indices if i is not None and str(i).strip() != ''}
    items, meta = [], {}
    for idx, row in df.iterrows():
        if sel is not None and int(idx) not in sel:
            continue
        img_path = str(row.get('img_path') or '').strip()
        if not img_path:
            continue
        items.append(img_path)
        meta[img_path] = {
            'source_detail_id': _safe_int(row.get('id')),
            'origin_object_key': _safe_str(row.get('origin_object_key')),
            'product_no': _safe_str(row.get('product_no')),
            'product_id': _safe_str(row.get('product_id')),
            'product_type': _safe_str(row.get('product_type')) or _safe_str(row.get('result_product_type')),
            'position': _safe_str(row.get('position')),
        }
    return items, meta


def _items_from_dir(path):
    items, meta = [], {}
    for root, _, files in os.walk(path):
        for fn in files:
            if fn.lower().endswith(IMG_EXTS):
                p = os.path.join(root, fn)
                items.append(p)
                meta[p] = {}
    return items, meta


def _items_from_paths(paths):
    items, meta = [], {}
    for p in paths or []:
        p = str(p).strip()
        if p:
            items.append(p)
            meta[p] = {}
    return items, meta


def build_predict_items(image_source):
    """根据 image_source 返回 (items, items_meta)。
    image_source: {type:'task'|'dir'|'paths'|'sync_dataset', ...}
    """
    src_type = (image_source or {}).get('type')
    if src_type == 'task':
        return _items_from_task(
            image_source.get('task_id'),
            selected_indices=image_source.get('selected_indices'),
        )
    if src_type == 'dir':
        return _items_from_dir(image_source.get('path') or '')
    if src_type == 'paths':
        return _items_from_paths(image_source.get('paths'))
    if src_type == 'sync_dataset':
        return _items_from_sync_dataset(image_source.get('sync_dataset_id'))
    raise ValueError(f'不支持的 image_source.type: {src_type}')


def _items_from_sync_dataset(sync_dataset_id):
    """从已同步的训练平台数据集目录收集图片路径。"""
    from studio.sync.forge_sync import resolve_dataset_output_dir
    ds = forge_db.get_sync_dataset(sync_dataset_id)
    if not ds:
        raise ValueError(f'数据集不存在: {sync_dataset_id}')
    project = forge_db.get_sync_project(ds['project_id'])
    if not project:
        raise ValueError(f'数据集所属项目不存在: {ds["project_id"]}')
    out_dir = resolve_dataset_output_dir(project, ds)
    items, meta = _items_from_dir(out_dir)
    if not items:
        raise ValueError(f'数据集「{ds.get("name")}」本地目录无图片，请先同步')
    return items, meta


def import_deploy_model(deploy_id, approach_id, client=None, config=None):
    """将 vision_backend.modeldeploy 一行导入 model_registry，返回 registry id。"""
    from server.core import load_config, get_db_client
    from studio.query.deployed_models import fetch_deployed_models
    config = config or load_config()
    client = client or get_db_client()
    bundle = fetch_deployed_models(client, config, approach_id=int(approach_id), limit=200)
    dm = next(
        (m for m in (bundle.get('models') or []) if int(m.get('id') or 0) == int(deploy_id)),
        None,
    )
    if not dm:
        raise ValueError(f'未找到部署模型 #{deploy_id}')
    if not dm.get('full_path') or not dm.get('path_resolvable'):
        name = dm.get('deploy_name') or deploy_id
        raise ValueError(f'部署模型「{name}」无法解析权重路径，请检查平台根路径配置')
    return import_model({
        'name': dm.get('deploy_name'),
        'checkpoint_path': dm['full_path'],
        'model_type': dm.get('model_type'),
        'labels': dm.get('labels'),
        'source': 'modeldeploy',
        'source_ref': str(deploy_id),
        'approach_id': int(approach_id),
    })


def import_train_model(train_id, approach_id, client=None, config=None, skip_missing=False):
    """将 vision_backend.modeltrainconfig 一行导入 model_registry，返回 registry id。"""
    from server.core import load_config, get_db_client
    from studio.query.deployed_models import fetch_training_models
    config = config or load_config()
    client = client or get_db_client()
    bundle = fetch_training_models(client, config, approach_id=int(approach_id), limit=200)
    tm = next(
        (m for m in (bundle.get('models') or []) if int(m.get('id') or 0) == int(train_id)),
        None,
    )
    if not tm:
        raise ValueError(f'未找到训练模型 #{train_id}')
    path = str(tm.get('full_path') or tm.get('hint_path') or '').strip()
    if not path:
        name = tm.get('model_name') or train_id
        raise ValueError(f'训练模型「{name}」无法解析权重路径')
    if not os.path.isfile(path):
        if skip_missing:
            return None
        name = tm.get('model_name') or train_id
        raise ValueError(f'训练模型「{name}」权重文件不存在：{path}')
    return import_model({
        'name': tm.get('model_name'),
        'checkpoint_path': path,
        'model_type': tm.get('model_type'),
        'labels': tm.get('labels'),
        'source': 'modeltrainconfig',
        'source_ref': str(train_id),
        'approach_id': int(approach_id),
    })


def import_all_platform_models(
    approach_id=None,
    deploy_approach_id=None,
    train_approach_id=None,
    include_deploy=True,
    include_train=True,
    limit=200,
    client=None,
    config=None,
):
    """批量将本地总控部署/训练模型导入 model_registry。"""
    from server.core import load_config, get_db_client
    from studio.query.approach_context import resolve_local_approach_id
    from studio.query.deployed_models import fetch_deployed_models, fetch_training_models
    config = config or load_config()
    client = client or get_db_client()
    deploy_aid = resolve_local_approach_id(config, override=deploy_approach_id or approach_id)
    train_aid = resolve_local_approach_id(
        config, override=train_approach_id or approach_id or deploy_approach_id,
    )
    imported, skipped, failed = [], [], []

    if include_deploy:
        bundle = fetch_deployed_models(client, config, approach_id=deploy_aid, limit=limit)
        for dm in bundle.get('models') or []:
            if not dm.get('path_resolvable'):
                skipped.append({
                    'source': 'modeldeploy',
                    'id': dm.get('id'),
                    'name': dm.get('deploy_name'),
                    'reason': '路径不可用',
                })
                continue
            try:
                mid = import_deploy_model(dm['id'], deploy_aid, client=client, config=config)
                imported.append({
                    'source': 'modeldeploy',
                    'id': dm.get('id'),
                    'name': dm.get('deploy_name'),
                    'registry_id': mid,
                })
            except Exception as e:  # noqa: BLE001
                failed.append({
                    'source': 'modeldeploy',
                    'id': dm.get('id'),
                    'name': dm.get('deploy_name'),
                    'error': str(e),
                })

    if include_train:
        bundle = fetch_training_models(client, config, approach_id=train_aid, limit=limit)
        for tm in bundle.get('models') or []:
            if not tm.get('path_resolvable'):
                skipped.append({
                    'source': 'modeltrainconfig',
                    'id': tm.get('id'),
                    'name': tm.get('model_name'),
                    'reason': '权重文件不存在',
                })
                continue
            try:
                mid = import_train_model(tm['id'], train_aid, client=client, config=config)
                if mid is None:
                    skipped.append({
                        'source': 'modeltrainconfig',
                        'id': tm.get('id'),
                        'name': tm.get('model_name'),
                        'reason': '权重文件不存在',
                    })
                    continue
                imported.append({
                    'source': 'modeltrainconfig',
                    'id': tm.get('id'),
                    'name': tm.get('model_name'),
                    'registry_id': mid,
                })
            except Exception as e:  # noqa: BLE001
                failed.append({
                    'source': 'modeltrainconfig',
                    'id': tm.get('id'),
                    'name': tm.get('model_name'),
                    'error': str(e),
                })

    return {
        'imported': imported,
        'skipped': skipped,
        'failed': failed,
        'imported_count': len(imported),
        'skipped_count': len(skipped),
        'failed_count': len(failed),
    }


def enqueue_predict_job(model_id, name, image_source, threshold=None,
                        device=None, max_size=None, intra_concurrency=1, priority=100,
                        extra_params=None):
    model = forge_db.get_model(model_id)
    if not model:
        raise ValueError(f'模型不存在: {model_id}')
    items, meta = build_predict_items(image_source)
    if not items:
        raise ValueError('未找到任何待预测图片')
    params = {
        'model_id': int(model_id),
        'image_source': image_source,
        'items_meta': meta,
    }
    if extra_params:
        params.update(extra_params)
    if threshold is not None:
        params['threshold'] = float(threshold)
    if device:
        params['device'] = device
    if max_size is not None:
        params['max_size'] = int(max_size)
    job_id = forge_db.create_job(
        job_type='predict',
        name=name or f"predict-{model.get('name')}",
        params=params,
        items=items,
        priority=priority,
        intra_concurrency=intra_concurrency,
    )
    from studio.forge import job_log
    job_log.clear(job_id)
    job_log.append(job_id, f'已创建预测作业，共 {len(items)} 张，等待 worker 领取 …')
    return {'job_id': job_id, 'total': len(items)}


def enqueue_platform_predict_job(
    train_id,
    model_name,
    image_source,
    name=None,
    threshold=None,
    batch_size=None,
    priority=100,
    extra_params=None,
):
    """训练模型：走 Magic-Fox model_validation API，无需导入 model_registry。"""
    items, meta = build_predict_items(image_source)
    if not items:
        raise ValueError('未找到任何待预测图片')
    params = {
        'predict_mode': 'platform_validation',
        'train_id': int(train_id),
        'model_name': model_name or f'train-{train_id}',
        'image_source': image_source,
        'items_meta': meta,
        'threshold': float(threshold if threshold is not None else 0.1),
    }
    if batch_size is not None:
        params['batch_size'] = int(batch_size)
    if extra_params:
        params.update(extra_params)
    job_id = forge_db.create_job(
        job_type='predict',
        name=name or f'platform-{model_name or train_id}',
        params=params,
        items=items,
        priority=priority,
        intra_concurrency=1,
    )
    return {'job_id': job_id, 'total': len(items), 'train_id': int(train_id)}


def _resolve_train_model_name(train_id, approach_id, project_id=None, client=None, config=None):
    from studio.sync import platform_models
    name = platform_models.resolve_train_model_name(
        train_id, project_id=project_id, approach_id=approach_id,
    )
    if name and name != f'train-{train_id}':
        return name
    from server.core import load_config, get_db_client
    from studio.query.deployed_models import fetch_training_models
    config = config or load_config()
    client = client or get_db_client()
    bundle = fetch_training_models(client, config, approach_id=int(approach_id), limit=500)
    tm = next(
        (m for m in (bundle.get('models') or []) if int(m.get('id') or 0) == int(train_id)),
        None,
    )
    if tm:
        return tm.get('model_name') or f'train-{train_id}'
    return name


def enqueue_predict_jobs_batch(
    model_ids=None,
    deploy_model_ids=None,
    train_model_ids=None,
    image_source=None,
    sync_dataset_id=None,
    name_prefix=None,
    threshold=None,
    device=None,
    max_size=None,
    intra_concurrency=1,
    priority=100,
    platform_project_id=None,
):
    """多模型批量创建 predict 作业：每个模型独立一个 job（各自 load_model 一次）。"""
    ds = None
    project = None
    if sync_dataset_id:
        ds = forge_db.get_sync_dataset(int(sync_dataset_id))
        if not ds:
            raise ValueError(f'数据集不存在: {sync_dataset_id}')
        project = forge_db.get_sync_project(ds['project_id'])
        image_source = {
            'type': 'sync_dataset',
            'sync_dataset_id': int(sync_dataset_id),
        }
    elif platform_project_id and not project:
        project = forge_db.get_sync_project(int(platform_project_id))
    if not image_source:
        raise ValueError('缺少 image_source 或 sync_dataset_id')

    items, meta = build_predict_items(image_source)
    if not items:
        raise ValueError('未找到任何待预测图片')

    from server.core import load_config
    from studio.query.approach_context import resolve_local_approach_id, resolve_magic_fox_approach_id

    cfg = load_config()
    local_approach_id = resolve_local_approach_id(cfg)
    magic_fox_approach_id = resolve_magic_fox_approach_id(project)

    registry_ids = [int(x) for x in (model_ids or []) if x]
    if deploy_model_ids:
        if not local_approach_id:
            raise ValueError('导入部署模型需要在设置中配置 defect_approach_id（本地总控 Approach）')
        for did in deploy_model_ids:
            registry_ids.append(import_deploy_model(did, local_approach_id, client=None, config=cfg))

    train_ids = [int(x) for x in (train_model_ids or []) if x]
    if train_ids and not magic_fox_approach_id:
        raise ValueError('训练模型预测需要关联 Magic-Fox 项目并配置 approach_id')

    seen = set()
    unique_registry = []
    for mid in registry_ids:
        if mid not in seen:
            seen.add(mid)
            unique_registry.append(mid)

    if not unique_registry and not train_ids:
        raise ValueError('请至少选择一个模型')

    extra = {}
    if sync_dataset_id:
        extra['sync_dataset_id'] = int(sync_dataset_id)
    if platform_project_id:
        extra['platform_project_id'] = int(platform_project_id)

    prefix = (name_prefix or '').strip() or (ds.get('name') if ds else 'predict')
    jobs = []

    for tid in train_ids:
        model_name = _resolve_train_model_name(
            tid, magic_fox_approach_id, project_id=platform_project_id,
        )
        job_name = f'{prefix} · {model_name}'
        result = enqueue_platform_predict_job(
            train_id=tid,
            model_name=model_name,
            image_source=image_source,
            name=job_name,
            threshold=threshold if threshold is not None else 0.1,
            priority=priority,
            extra_params=extra or None,
        )
        jobs.append({
            'job_id': result['job_id'],
            'train_id': tid,
            'model_name': model_name,
            'total': result['total'],
            'predict_mode': 'platform_validation',
        })

    for mid in unique_registry:
        model = forge_db.get_model(mid)
        if not model:
            raise ValueError(f'模型不存在: {mid}')
        job_name = f'{prefix} · {model.get("name")}'
        result = enqueue_predict_job(
            model_id=mid,
            name=job_name,
            image_source=image_source,
            threshold=threshold,
            device=device,
            max_size=max_size,
            intra_concurrency=intra_concurrency,
            priority=priority,
            extra_params=extra or None,
        )
        jobs.append({
            'job_id': result['job_id'],
            'model_id': mid,
            'model_name': model.get('name'),
            'total': result['total'],
        })
    return {
        'jobs': jobs,
        'total_images': len(items),
        'model_count': len(jobs),
    }


def enqueue_export_job(export_params, name=None, priority=50):
    """把人工质检导出放进后台作业（大批量异步化）。export_params 透传给 forge_manual_qc.export_records。"""
    params = {'export': dict(export_params or {})}
    job_id = forge_db.create_job(
        job_type='manual_qc_export',
        name=name or 'manual-qc-export',
        params=params,
        items=['export'],
        priority=priority,
    )
    return {'job_id': job_id, 'total': 1}


def enqueue_manual_qc_job(entries, name=None, batch_id=None, priority=100):
    if not entries:
        raise ValueError('entries 不能为空')
    items = [str(i) for i in range(len(entries))]
    params = {'entries': entries, 'batch_id': batch_id}
    job_id = forge_db.create_job(
        job_type='manual_qc_archive',
        name=name or 'manual-qc-batch',
        params=params,
        items=items,
        priority=priority,
    )
    return {'job_id': job_id, 'total': len(entries)}


def enqueue_dataset_sync(dataset_id, name=None, priority=80):
    """将数据集同步放入后台作业。"""
    ds = forge_db.get_sync_dataset(dataset_id)
    if not ds:
        raise ValueError(f'数据集不存在: {dataset_id}')
    if not ds.get('enabled', 1):
        raise ValueError('数据集已禁用')
    params = {'sync_dataset_id': int(dataset_id)}
    job_id = forge_db.create_job(
        job_type='dataset_sync',
        name=name or f"sync-{ds.get('name') or dataset_id}",
        params=params,
        items=['sync'],
        priority=priority,
    )
    forge_db.update_sync_dataset_stats(int(dataset_id), last_sync_job_id=job_id, last_sync_at=False)
    from studio.forge import job_log
    job_log.clear(job_id)
    job_log.append(job_id, f'排队同步数据集 #{dataset_id}「{ds.get("name")}」')
    return {'job_id': job_id, 'total': 1, 'dataset_id': int(dataset_id)}


def _safe_int(v):
    try:
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_str(v):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ''
    s = str(v).strip()
    return '' if s.lower() == 'nan' else s
