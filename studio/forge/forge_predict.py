"""预测作业处理器：load_model 一次 → 逐图 predict_one → 写 predict_result（可续跑）。

默认通过**外部 Python 子进程**调用 DetUnify-Studio/scripts/predict_job_worker.py
（配置 predict_python_executable + detunify_studio_root），与主程序环境隔离、复用机器已有 torch 环境。

未配置 predict_python_executable 时回退为进程内 import model_api（开发/单测）。
"""
import os
import sys
import threading

from studio.forge import forge_db
from studio.forge import job_log
from studio.forge import predict_runtime
from studio.paths import PROJECT_ROOT as BASE_DIR

MAX_ITEM_ATTEMPTS = 3

_device_sems = {}
_device_sems_lock = threading.Lock()


def detunify_predict_dir(config=None):
    """兼容单测：DetUnify src/predict 目录。"""
    s = predict_runtime.resolve_predict_settings(config)
    if s.get('predict_src_dir') and os.path.isdir(s['predict_src_dir']):
        return s['predict_src_dir']
    return os.path.normpath(os.path.join(BASE_DIR, '..', 'DetUnify-Studio', 'src', 'predict'))


# 单测仍引用此常量
DETUNIFY_PREDICT_DIR = detunify_predict_dir()


def _device_max_concurrency():
    try:
        from server.core import load_config
        return max(1, int(load_config().get('device_max_concurrency', 1)))
    except Exception:
        return 1


def _device_sem(device):
    key = str(device or 'default')
    with _device_sems_lock:
        sem = _device_sems.get(key)
        if sem is None:
            sem = threading.Semaphore(_device_max_concurrency())
            _device_sems[key] = sem
        return sem


def _import_model_api():
    """进程内预测（未配置子进程时）。"""
    predict_dir = detunify_predict_dir()
    if predict_dir not in sys.path:
        sys.path.insert(0, predict_dir)
    import model_api  # type: ignore
    return model_api


def _use_subprocess(config=None):
    return predict_runtime.resolve_predict_settings(config).get('use_subprocess')


def health_check_model(model, device=None, config=None):
    """尝试加载模型并立即释放，验证权重可用。"""
    device = device or (model.get('default_params') or {}).get('device') or 'cuda:0'
    info = {'ok': False, 'framework': model.get('framework'), 'device': device}
    threshold = float((model.get('default_params') or {}).get('threshold', 0.5))
    max_size = int((model.get('default_params') or {}).get('max_size', 1536))

    if _use_subprocess(config):
        try:
            hc = predict_runtime.run_health_check(
                model, device=device, threshold=threshold, max_size=max_size, config=config,
            )
            info.update(hc)
        except Exception as e:  # noqa: BLE001
            info['error'] = str(e)
        return info

    try:
        api = _import_model_api()
        loaded = api.load_model(
            model['checkpoint_path'], framework=model.get('framework'),
            sub_type=model.get('sub_type'), device=device,
            max_size=max_size, threshold=threshold,
        )
        try:
            loaded.release()
        except Exception:
            pass
        info['ok'] = True
    except Exception as e:  # noqa: BLE001
        info['error'] = str(e)
    return info


def _meta_for(params, ref_key):
    meta_map = (params or {}).get('items_meta') or {}
    return meta_map.get(ref_key) or {}


def _build_ext(predictions):
    return {'original_predictions': predictions}


def run_predict_job(job, stop_check=None, on_progress=None, model_loader=None):
    """执行一个 predict 作业。"""
    params = job.get('params') or {}
    model_id = params.get('model_id')
    model = forge_db.get_model(model_id) if model_id else None
    if not model:
        raise ValueError(f'模型未注册或不存在: model_id={model_id}')

    threshold = float(params.get('threshold', (model.get('default_params') or {}).get('threshold', 0.5)))
    device = params.get('device') or (model.get('default_params') or {}).get('device') or 'cuda:0'
    max_size = int(params.get('max_size', (model.get('default_params') or {}).get('max_size', 1536)))
    intra = max(1, int(job.get('intra_concurrency') or params.get('intra_concurrency') or 1))
    pending_n = len(forge_db.pending_items(job['id']))

    job_log.append(
        job['id'],
        f'预测开始：模型 {model.get("name")} ({model.get("framework")}) · '
        f'待处理 {pending_n} 张 · device={device} · threshold={threshold} · intra={intra}',
    )

    if model_loader:
        loaded = model_loader() if callable(model_loader) else model_loader
        return _run_with_loaded(job, loaded, model, params, threshold, intra, stop_check, on_progress)

    settings = predict_runtime.resolve_predict_settings()
    if settings.get('use_subprocess'):
        if settings.get('predict_subprocess_auto'):
            job_log.append(
                job['id'],
                f'子进程预测（自动）· {settings.get("predict_python_executable") or "python"}',
            )
        sem = _device_sem(device)
        sem.acquire()
        try:
            return _run_predict_subprocess(job, model, params, threshold, device, max_size, stop_check, on_progress)
        finally:
            sem.release()

    if settings.get('predict_script') and os.path.isfile(settings['predict_script']):
        job_log.append(
            job['id'],
            '警告：未启用子进程预测，进程内加载 mmdet 在 worker 线程可能失败；'
            '请在设置中填写 predict_python_executable 或取消 PC_FORCE_INPROCESS_PREDICT',
        )

    loader = lambda: _import_model_api().load_model(
        model['checkpoint_path'], framework=model.get('framework'),
        sub_type=model.get('sub_type'), device=device,
        max_size=max_size, threshold=threshold,
    )
    sem = _device_sem(device)
    sem.acquire()
    try:
        job_log.append(job['id'], '进程内加载模型 …')
        loaded = loader()
        job_log.append(job['id'], '模型加载完成，开始逐图预测')
        return _run_with_loaded(job, loaded, model, params, threshold, intra, stop_check, on_progress)
    finally:
        sem.release()


def _run_predict_subprocess(job, model, params, threshold, device, max_size, stop_check, on_progress):
    items = forge_db.pending_items(job['id'])
    if stop_check and stop_check():
        return forge_db.recompute_job_progress(job['id'])

    payload = {
        'model': {
            'checkpoint_path': model['checkpoint_path'],
            'framework': model.get('framework'),
            'sub_type': model.get('sub_type'),
        },
        'device': device,
        'threshold': threshold,
        'max_size': max_size,
        'images': [{'path': item['ref_key'], 'threshold': threshold} for item in items],
    }
    timeout = max(3600, len(items) * 120)
    job_log.append(
        job['id'],
        f'子进程批量预测 {len(items)} 张（加载模型 + 推理，期间日志可能较少）…',
    )

    def _subprocess_log(line):
        line = str(line or '').strip()
        if line:
            job_log.append_throttled(job['id'], f'[predict] {line}', key='subprocess', min_interval=3.0)

    batch_results = predict_runtime.run_batch_predict(
        payload, timeout=timeout, log_line=_subprocess_log,
    )
    job_log.append(job['id'], f'子进程预测返回 {len(batch_results)} 条结果，开始写库 …')
    by_path = {r.get('path'): r for r in batch_results}

    for item in items:
        if stop_check and stop_check():
            break
        img_path = item['ref_key']
        forge_db.mark_item_running(item['id'])
        res = by_path.get(img_path)
        if not res:
            forge_db.mark_item_failed(item['id'], error='子进程未返回该图结果', max_attempts=MAX_ITEM_ATTEMPTS)
            continue
        if not res.get('ok'):
            forge_db.mark_item_failed(item['id'], error=res.get('error') or 'predict failed', max_attempts=MAX_ITEM_ATTEMPTS)
            continue
        predictions = res.get('predictions') or []
        meta = _meta_for(params, img_path)
        max_score = max((p.get('confidence', 0) for p in predictions), default=None)
        row = {
            'job_id': job['id'],
            'model_id': model['id'],
            'model_name': model.get('name'),
            'source_detail_id': meta.get('source_detail_id'),
            'origin_object_key': meta.get('origin_object_key'),
            'img_path': img_path,
            'product_no': meta.get('product_no'),
            'product_id': meta.get('product_id'),
            'product_type': meta.get('product_type'),
            'position': meta.get('position'),
            'img_width': res.get('width'),
            'img_height': res.get('height'),
            'ext': _build_ext(predictions),
            'box_count': len(predictions),
            'max_score': max_score,
            'threshold': threshold,
            'predict_status': 'done',
        }
        result_id = forge_db.insert_predict_result(row)
        forge_db.mark_item_done(item['id'], result_ref=result_id)
        forge_db.recompute_job_progress(job['id'])
        if on_progress:
            on_progress()

    return forge_db.recompute_job_progress(job['id'])


def _run_with_loaded(job, loaded, model, params, threshold, intra, stop_check, on_progress):
    items = forge_db.pending_items(job['id'])
    write_lock = threading.Lock()

    def process(item):
        if stop_check and stop_check():
            return 'stopped'
        img_path = item['ref_key']
        forge_db.mark_item_running(item['id'])
        try:
            out = loaded.predict_one(img_path, threshold=threshold)
            predictions = out.get('predictions', [])
            meta = _meta_for(params, img_path)
            max_score = max((p.get('confidence', 0) for p in predictions), default=None)
            row = {
                'job_id': job['id'],
                'model_id': model['id'],
                'model_name': model.get('name'),
                'source_detail_id': meta.get('source_detail_id'),
                'origin_object_key': meta.get('origin_object_key'),
                'img_path': img_path,
                'product_no': meta.get('product_no'),
                'product_id': meta.get('product_id'),
                'product_type': meta.get('product_type'),
                'position': meta.get('position'),
                'img_width': out.get('width'),
                'img_height': out.get('height'),
                'ext': _build_ext(predictions),
                'box_count': len(predictions),
                'max_score': max_score,
                'threshold': threshold,
                'predict_status': 'done',
            }
            with write_lock:
                result_id = forge_db.insert_predict_result(row)
                forge_db.mark_item_done(item['id'], result_ref=result_id)
            return 'done'
        except Exception as e:  # noqa: BLE001
            with write_lock:
                forge_db.mark_item_failed(item['id'], error=str(e), max_attempts=MAX_ITEM_ATTEMPTS)
            return 'failed'

    if intra > 1 and len(items) > 1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=intra) as pool:
            for outcome in pool.map(process, items):
                if outcome == 'stopped':
                    break
                forge_db.recompute_job_progress(job['id'])
                if on_progress:
                    on_progress()
    else:
        for item in items:
            outcome = process(item)
            forge_db.recompute_job_progress(job['id'])
            if on_progress:
                on_progress()
            if outcome == 'stopped':
                break

    try:
        loaded.release()
    except Exception:
        pass

    return forge_db.recompute_job_progress(job['id'])
