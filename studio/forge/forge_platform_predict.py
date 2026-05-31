"""Magic-Fox 线上 model_validation API 预测（训练模型 train_id，无需本地权重/注册表导入）。"""
import json
import logging
import mimetypes
import os
import time
from pathlib import Path

import requests

from studio.forge import forge_db
from studio.sync import magic_fox_bridge as mf

logger = logging.getLogger('detforge.platform_predict')

DEFAULT_PREDICT_BATCH = 10
UPLOAD_CHUNK = 3
UPLOAD_CONNECT_TIMEOUT = 30
UPLOAD_READ_TIMEOUT = 1800
UPLOAD_WRITE_TIMEOUT = 1800
POLL_INTERVAL = 3.0
POLL_MAX_WAIT = 3600.0
MODEL_LOAD_MAX_WAIT = 600.0


def _clamp_int(val, default, lo, hi):
    try:
        n = int(val)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def resolve_platform_predict_settings(config=None):
    """从 config.json 解析平台预测上传参数（设置页可配置）。"""
    cfg = mf._cfg(config)
    return {
        'platform_predict_batch_size': _clamp_int(
            cfg.get('platform_predict_batch_size'), DEFAULT_PREDICT_BATCH, 1, 50,
        ),
        'platform_upload_chunk': _clamp_int(
            cfg.get('platform_upload_chunk'), UPLOAD_CHUNK, 1, 20,
        ),
        'platform_upload_connect_timeout': _clamp_int(
            cfg.get('platform_upload_connect_timeout'), UPLOAD_CONNECT_TIMEOUT, 5, 300,
        ),
        'platform_upload_read_timeout': _clamp_int(
            cfg.get('platform_upload_read_timeout'), UPLOAD_READ_TIMEOUT, 30, 7200,
        ),
        'platform_upload_write_timeout': _clamp_int(
            cfg.get('platform_upload_write_timeout'), UPLOAD_WRITE_TIMEOUT, 30, 7200,
        ),
    }


def _noop_log(_msg):
    pass


def _file_size_bytes(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _fmt_bytes(n):
    n = int(n or 0)
    if n >= 1048576:
        return f'{n / 1048576:.2f} MB'
    if n >= 1024:
        return f'{n / 1024:.1f} KB'
    return f'{n} B'


def _fmt_settings(s):
    return (
        f'batch={s["platform_predict_batch_size"]}, '
        f'upload_chunk={s["platform_upload_chunk"]}, '
        f'timeout(connect/read/write)='
        f'{s["platform_upload_connect_timeout"]}/'
        f'{s["platform_upload_read_timeout"]}/'
        f'{s["platform_upload_write_timeout"]}s'
    )


def _log_both(log_fn, msg):
    log_fn(msg)
    logger.info(msg)


def _api_base(config=None):
    cfg = mf._cfg(config)
    return str(cfg.get('magic_fox_api_base') or 'https://www.ai.magic-fox.com/api/v1').rstrip('/')


def _session():
    s = requests.Session()
    s.trust_env = False
    return s


def _auth_headers(token):
    return {'Authorization': f'Bearer {token}'}


def _json_headers(token):
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }


def _check_api(data, step):
    if not data.get('success') or data.get('code') != 200:
        raise RuntimeError(
            f'[{step}] Magic-Fox 接口失败: code={data.get("code")}, msg={data.get("msg", "未知错误")}',
        )


def wait_model_loaded(train_id, token, base, session, max_wait=MODEL_LOAD_MAX_WAIT, log=None):
    """轮询直到模型 status=loaded。"""
    log = log or _noop_log
    url = f'{base}/model_validation/{train_id}'
    start = time.time()
    poll = 0
    log(f'等待模型加载 train_id={train_id} url={url} max_wait={max_wait}s')
    while True:
        poll += 1
        t0 = time.time()
        resp = session.get(url, headers=_auth_headers(token), params={'train_id': train_id}, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _check_api(data, 'check_model_status')
        status = str((data.get('data') or {}).get('status') or '')
        elapsed = time.time() - start
        log(
            f'  模型状态轮询 #{poll}: status={status!r} '
            f'耗时 {time.time() - t0:.2f}s · 累计 {elapsed:.1f}s',
        )
        if status == 'loaded':
            log(f'模型已加载 train_id={train_id} · 共轮询 {poll} 次 · {elapsed:.1f}s')
            return status
        if time.time() - start >= max_wait:
            raise RuntimeError(f'训练模型 #{train_id} 未在 {max_wait}s 内加载完成（当前 {status!r}）')
        time.sleep(10.0)


def _upload_timeout(settings=None):
    s = settings or resolve_platform_predict_settings()
    connect = s['platform_upload_connect_timeout']
    read = s['platform_upload_read_timeout']
    write = s['platform_upload_write_timeout']
    try:
        import urllib3
        return urllib3.Timeout(connect=connect, read=read, write=write)
    except Exception:
        return (connect, read)


def _post_upload(session, url, token, multipart, settings=None):
    return session.post(
        url,
        headers=_auth_headers(token),
        files=multipart,
        timeout=_upload_timeout(settings),
    )


def _upload_one_file(path, token, base, session, settings=None, log=None):
    log = log or _noop_log
    url = f'{base}/objects/upload_files/'
    p = Path(path)
    size = _file_size_bytes(p)
    t0 = time.time()
    log(f'    ↑ 单张上传: {p.name} ({_fmt_bytes(size)})')
    ctype = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
    with open(p, 'rb') as f:
        multipart = [('files', (p.name, f, ctype))]
        resp = _post_upload(session, url, token, multipart, settings=settings)
    resp.raise_for_status()
    data = resp.json()
    _check_api(data, 'upload_files')
    batch_result = data.get('data') or []
    if not isinstance(batch_result, list) or not batch_result:
        raise RuntimeError(f'upload_files 单张上传无返回: {p.name}')
    item = batch_result[0]
    log(
        f'    ✓ 单张上传完成: {p.name} · object_key={item.get("object_key")!r} '
        f'· {time.time() - t0:.2f}s',
    )
    return item


def upload_files(file_paths, token, base, session, chunk_size=None, settings=None, log=None):
    log = log or _noop_log
    s = settings or resolve_platform_predict_settings()
    chunk = max(1, int(chunk_size or s['platform_upload_chunk']))
    url = f'{base}/objects/upload_files/'
    all_uploaded = []
    paths = [Path(p) for p in file_paths]
    total_chunks = (len(paths) + chunk - 1) // chunk if paths else 0
    log(
        f'  开始上传 {len(paths)} 张 · chunk={chunk} · 共 {total_chunks} 次 multipart · '
        f'timeout={_fmt_settings(s)}',
    )
    for chunk_idx, batch_start in enumerate(range(0, len(paths), chunk), start=1):
        batch = paths[batch_start: batch_start + chunk]
        batch_bytes = sum(_file_size_bytes(p) for p in batch)
        names = [p.name for p in batch]
        log(
            f'  上传分片 {chunk_idx}/{total_chunks}: {len(batch)} 张 · '
            f'{_fmt_bytes(batch_bytes)} · {", ".join(names)}',
        )
        opened = []
        multipart = []
        t0 = time.time()
        try:
            for p in batch:
                f = open(p, 'rb')
                opened.append(f)
                ctype = mimetypes.guess_type(p.name)[0] or 'application/octet-stream'
                multipart.append(('files', (p.name, f, ctype)))
            try:
                resp = _post_upload(session, url, token, multipart, settings=s)
                resp.raise_for_status()
                data = resp.json()
                _check_api(data, 'upload_files')
                batch_result = data.get('data') or []
                if not isinstance(batch_result, list):
                    raise RuntimeError(f'upload_files 返回 data 非列表: {type(batch_result)}')
                keys = [str(x.get('object_key') or '') for x in batch_result]
                log(
                    f'  ✓ 分片 {chunk_idx} 批量上传成功 · {len(batch_result)} 张 · '
                    f'{time.time() - t0:.2f}s · keys={keys}',
                )
                all_uploaded.extend(batch_result)
            except (requests.exceptions.Timeout, TimeoutError, OSError) as e:
                log(
                    f'  ✗ 分片 {chunk_idx} 批量上传失败 ({time.time() - t0:.2f}s): '
                    f'{type(e).__name__}: {e} · 降级逐张上传',
                )
                logger.warning(
                    '批量上传 %s 张超时/中断，改为逐张上传: %s',
                    len(batch), e,
                )
                for p in batch:
                    all_uploaded.append(
                        _upload_one_file(p, token, base, session, settings=s, log=log),
                    )
        finally:
            for f in opened:
                try:
                    f.close()
                except Exception:
                    pass
    log(f'  上传完成: 共 {len(all_uploaded)}/{len(paths)} 张')
    return all_uploaded


def delete_old_predictions(train_id, token, base, session, log=None):
    log = log or _noop_log
    url = f'{base}/model_validation/delete_model_validation_predictions/{train_id}'
    log(f'  清空平台旧预测 train_id={train_id}')
    try:
        t0 = time.time()
        resp = session.delete(url, headers=_auth_headers(token), timeout=30)
        resp.raise_for_status()
        log(f'  ✓ 清空平台旧预测完成 · HTTP {resp.status_code} · {time.time() - t0:.2f}s')
    except Exception as e:
        log(f'  ⚠ 清空平台旧预测失败: {type(e).__name__}: {e}')
        logger.warning('清空平台旧预测失败 train_id=%s: %s', train_id, e)


def submit_batch_validation(uploaded_items, train_id, threshold, token, base, session, log=None):
    log = log or _noop_log
    images = []
    for item in uploaded_items:
        object_key = str(item.get('object_key') or '')
        file_name = (
            item.get('file_name')
            or item.get('object_name')
            or Path(object_key).name
        )
        images.append({
            'object_key': object_key,
            'file_name': file_name,
            'file_path': file_name,
        })
    payload = {
        'images': images,
        'biz_id': int(train_id),
        'threshold': float(threshold),
        'type': 'validation',
    }
    log(
        f'  提交 batch_validation: train_id={train_id} threshold={threshold} '
        f'images={len(images)}',
    )
    t0 = time.time()
    resp = session.post(
        f'{base}/model_validation/batch_validation',
        headers=_json_headers(token),
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    _check_api(data, 'batch_validation')
    raw = data.get('data')
    if isinstance(raw, str) and raw:
        vid = raw
    elif isinstance(raw, dict):
        vid = raw.get('validation_id') or raw.get('id') or raw.get('task_id') or ''
        vid = str(vid) if vid else ''
    else:
        vid = ''
    if not vid:
        raise RuntimeError(f'batch_validation 未返回 validation_id: {data}')
    log(f'  ✓ batch_validation 已提交 validation_id={vid} · {time.time() - t0:.2f}s')
    return vid


def poll_validation_results(
    validation_id, token, base, session,
    poll_interval=POLL_INTERVAL, max_wait=POLL_MAX_WAIT, log=None,
):
    log = log or _noop_log
    ratio_url = f'{base}/model_validation/get_validation_ratio/{validation_id}'
    start = time.time()
    poll = 0
    last_ratio = -1.0
    log(f'  轮询 validation 进度 validation_id={validation_id} interval={poll_interval}s')
    while True:
        poll += 1
        t0 = time.time()
        resp = session.get(
            ratio_url,
            headers=_auth_headers(token),
            params={'validation_id': validation_id},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        raw = data.get('data', 0)
        ratio = float(raw) if isinstance(raw, (int, float)) else 0.0
        elapsed = time.time() - start
        if ratio != last_ratio or poll == 1 or poll % 10 == 0:
            log(
                f'    轮询 #{poll}: ratio={ratio:.2%} · 请求 {time.time() - t0:.2f}s · '
                f'累计 {elapsed:.1f}s',
            )
            last_ratio = ratio
        if ratio >= 1.0:
            log(f'  ✓ validation 完成 validation_id={validation_id} · {poll} 次轮询 · {elapsed:.1f}s')
            break
        if time.time() - start >= max_wait:
            log(f'  ⚠ validation 轮询超时 ratio={ratio:.2%} · {elapsed:.1f}s')
            logger.warning('validation %s 轮询超时 ratio=%.2f', validation_id, ratio)
            break
        time.sleep(poll_interval)
    return fetch_page_validations(validation_id, token, base, session, log=log)


def fetch_page_validations(validation_id, token, base, session, page_limit=50, log=None):
    log = log or _noop_log
    url = f'{base}/model_validation/page_validations/{validation_id}'
    all_items = []
    skip = 0
    page = 0
    log(f'  拉取 validation 结果 validation_id={validation_id} page_limit={page_limit}')
    while True:
        page += 1
        params = {
            'validation_id': validation_id,
            'limit': page_limit,
            'skip': skip,
            'sort_type': 'm_time',
            'fuzzy_name': '',
        }
        t0 = time.time()
        resp = session.get(url, headers=_auth_headers(token), params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        _check_api(data, 'page_validations')
        result_data = data.get('data') or {}
        total_count = int(result_data.get('total_count') or 0)
        validations = result_data.get('validations') or []
        for item in validations:
            pa = item.get('predict_annotations')
            if isinstance(pa, str):
                try:
                    item['predict_annotations'] = json.loads(pa)
                except Exception:
                    pass
        all_items.extend(validations)
        skip += len(validations)
        log(
            f'    页 #{page}: +{len(validations)} 条 · 累计 {len(all_items)}/{total_count} · '
            f'{time.time() - t0:.2f}s',
        )
        if not validations or skip >= total_count:
            break
    log(f'  ✓ 结果拉取完成: {len(all_items)} 条')
    return all_items


def _image_size(path):
    try:
        from PIL import Image
        with Image.open(path) as img:
            return int(img.width), int(img.height)
    except Exception:
        pass
    return 0, 0


def annotations_to_predictions(predict_annotations, threshold):
    pa = predict_annotations or {}
    if not isinstance(pa, dict):
        return []
    out = []
    for pred in pa.get('predictions') or []:
        conf = float(pred.get('confidence') or 0)
        if conf < threshold:
            continue
        pts = (pred.get('points') or [{}])[0]
        out.append({
            'name': pred.get('name'),
            'confidence': conf,
            'type': pred.get('type') or 'rect',
            'points': [{
                'x': float(pts.get('x') or 0),
                'y': float(pts.get('y') or 0),
                'w': float(pts.get('w') or 0),
                'h': float(pts.get('h') or 0),
            }],
        })
    return out


def _build_ext(predictions):
    return {'original_predictions': predictions}


def _meta_for(params, ref_key):
    meta_map = (params or {}).get('items_meta') or {}
    return meta_map.get(ref_key) or {}


def _result_by_filename(results):
    by_name = {}
    for item in results:
        obj_name = str(item.get('object_name') or item.get('dir_name') or '')
        file_name = Path(obj_name).name if obj_name else ''
        if file_name:
            by_name[file_name] = item
    return by_name


def _platform_model_id(train_id):
    """负 train_id 作为 predict_result.model_id，避免与注册表正 id 冲突。"""
    return -int(train_id)


def run_platform_predict_job(job, stop_check=None, on_progress=None, config=None):
    """执行 platform_validation 预测作业（params.train_id + predict_mode）。"""
    from studio.forge import job_log

    job_id = job['id']
    def log(msg):
        _log_both(lambda m: job_log.append(job_id, m), msg)

    params = job.get('params') or {}
    train_id = int(params.get('train_id') or 0)
    if not train_id:
        raise ValueError('platform_validation 作业缺少 train_id')
    model_name = str(params.get('model_name') or f'train-{train_id}')
    threshold = float(params.get('threshold', 0.1))
    pp_settings = resolve_platform_predict_settings(config)
    batch_size = max(
        1,
        int(params.get('batch_size') or pp_settings['platform_predict_batch_size']),
    )
    min_batch = max(1, pp_settings['platform_upload_chunk'])
    model_id = _platform_model_id(train_id)

    base, token = mf.get_api_token(config)
    base = base.rstrip('/')
    session = _session()
    job_started = time.time()

    log(
        f'平台预测开始 job=#{job_id} model={model_name} train_id={train_id} '
        f'threshold={threshold} api={base}',
    )
    log(f'上传/批处理配置: {_fmt_settings(pp_settings)} · 当前 batch_size={batch_size}')

    wait_model_loaded(train_id, token, base, session, log=log)

    items = forge_db.pending_items(job['id'])
    if not items:
        log('无待处理项，跳过')
        return forge_db.recompute_job_progress(job['id'])

    progress = forge_db.recompute_job_progress(job['id'])
    log(
        f'待处理 {len(items)} 张 · 作业进度 done={progress.get("done", 0)} '
        f'failed={progress.get("failed", 0)} total={progress.get("total", 0)}',
    )

    cleared_platform = False
    total_batches = (len(items) + batch_size - 1) // batch_size
    done_batches = 0

    for batch_start in range(0, len(items), batch_size):
        if stop_check and stop_check():
            log('收到停止信号，中断批次循环')
            break
        batch_items = items[batch_start: batch_start + batch_size]
        batch_paths = [it['ref_key'] for it in batch_items]
        batch_num = batch_start // batch_size + 1
        batch_bytes = sum(_file_size_bytes(p) for p in batch_paths)
        names_preview = ', '.join(Path(p).name for p in batch_paths[:8])
        if len(batch_paths) > 8:
            names_preview += f' …(+{len(batch_paths) - 8})'

        log(
            f'── 批次 {batch_num}/{total_batches} · {len(batch_items)} 张 · '
            f'{_fmt_bytes(batch_bytes)} ──',
        )
        log(f'  文件: {names_preview}')

        last_err = None
        for attempt in range(1, 4):
            batch_t0 = time.time()
            try:
                log(f'  尝试 {attempt}/3 · batch_size={batch_size}')
                if not cleared_platform:
                    delete_old_predictions(train_id, token, base, session, log=log)
                    cleared_platform = True
                uploaded = upload_files(
                    batch_paths, token, base, session, settings=pp_settings, log=log,
                )
                if not uploaded:
                    raise RuntimeError('上传图片失败')
                validation_id = submit_batch_validation(
                    uploaded, train_id, threshold, token, base, session, log=log,
                )
                results = poll_validation_results(
                    validation_id, token, base, session, log=log,
                )
                by_name = _result_by_filename(results)
                log(f'  平台返回 {len(results)} 条 · 可匹配文件名 {len(by_name)} 个')

                ok_n = fail_n = 0
                for item in batch_items:
                    if stop_check and stop_check():
                        log('收到停止信号，中断条目写入')
                        break
                    img_path = item['ref_key']
                    file_name = Path(img_path).name
                    forge_db.mark_item_running(item['id'])
                    row_item = by_name.get(file_name)
                    if not row_item:
                        fail_n += 1
                        err = f'平台未返回该图结果: {file_name}'
                        log(f'  ✗ item#{item["id"]} {file_name}: {err}')
                        forge_db.mark_item_failed(
                            item['id'],
                            error=err,
                            max_attempts=3,
                        )
                        continue
                    pa = row_item.get('predict_annotations') or {}
                    predictions = annotations_to_predictions(pa, threshold)
                    width, height = _image_size(img_path)
                    if isinstance(pa, dict):
                        width = int(pa.get('width') or width or 0) or width
                        height = int(pa.get('height') or height or 0) or height
                    meta = _meta_for(params, img_path)
                    max_score = max((p.get('confidence', 0) for p in predictions), default=None)
                    row = {
                        'job_id': job['id'],
                        'model_id': model_id,
                        'model_name': model_name,
                        'source_detail_id': meta.get('source_detail_id'),
                        'origin_object_key': meta.get('origin_object_key'),
                        'img_path': img_path,
                        'product_no': meta.get('product_no'),
                        'product_id': meta.get('product_id'),
                        'product_type': meta.get('product_type'),
                        'position': meta.get('position'),
                        'img_width': width or None,
                        'img_height': height or None,
                        'ext': _build_ext(predictions),
                        'box_count': len(predictions),
                        'max_score': max_score,
                        'threshold': threshold,
                        'predict_status': 'done',
                    }
                    result_id = forge_db.insert_predict_result(row)
                    forge_db.mark_item_done(item['id'], result_ref=result_id)
                    ok_n += 1
                    log(
                        f'  ✓ item#{item["id"]} {file_name}: '
                        f'{len(predictions)} 框 max={max_score} result_id={result_id}',
                    )

                progress = forge_db.recompute_job_progress(job['id'])
                done_batches += 1
                log(
                    f'── 批次 {batch_num} 完成 · ok={ok_n} fail={fail_n} · '
                    f'{time.time() - batch_t0:.1f}s · 作业 {progress.get("done", 0)}/'
                    f'{progress.get("total", 0)} ──',
                )
                if on_progress:
                    on_progress()
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                err_text = str(e).lower()
                is_timeout = (
                    isinstance(e, (requests.exceptions.Timeout, TimeoutError))
                    or 'timed out' in err_text
                    or 'timeout' in err_text
                )
                log(
                    f'  ✗ 批次 {batch_num} 尝试 {attempt}/3 失败 ({time.time() - batch_t0:.1f}s): '
                    f'{type(e).__name__}: {e}',
                )
                logger.warning(
                    'platform predict batch %s attempt %s failed job=%s: %s',
                    batch_num, attempt, job['id'], e,
                )
                if attempt >= 3:
                    for item in batch_items:
                        forge_db.mark_item_failed(item['id'], error=str(e), max_attempts=3)
                    log(f'批次 {batch_num} 已达最大重试，标记 {len(batch_items)} 项失败')
                    raise
                if is_timeout and batch_size > min_batch:
                    old = batch_size
                    batch_size = max(min_batch, batch_size // 2)
                    total_batches = (len(items) - batch_start + batch_size - 1) // batch_size
                    log(f'  检测到超时，batch_size {old} → {batch_size}')
                sleep_s = min(30.0, 2.0 * attempt)
                log(f'  {sleep_s:.0f}s 后重试…')
                time.sleep(sleep_s)

        if last_err:
            raise last_err

    final = forge_db.recompute_job_progress(job['id'])
    log(
        f'平台预测结束 job=#{job_id} · 批次 {done_batches}/{total_batches} · '
        f'done={final.get("done", 0)} failed={final.get("failed", 0)} · '
        f'总耗时 {time.time() - job_started:.1f}s',
    )
    return final
