"""查询结果 COCO 归档：后台任务 + 进度（内存 + 文件持久化）。"""
from __future__ import annotations

import json
import os
import re
import shutil
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from studio.export.csv2coco import build_coco_info
from studio.export.task_images import normalize_coco_images_for_task
from studio.timezone_util import format_iso_now, stamp_compact

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
JOBS_DIR = os.path.join(BASE_DIR, 'exports', 'archive_jobs')
MAX_JOBS = 60

PHASE_LABELS = {
    'preparing': '准备归档',
    'coco': '写入 COCO 标注',
    'images': '复制图片',
    'done': '完成',
}

_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_executor: ThreadPoolExecutor | None = None
_app = None
_product_name = 'DefectLoop Studio'


def _ensure_executor():
    global _executor
    if _executor is None:
        workers = max(1, int(os.environ.get('PC_ARCHIVE_WORKERS', '2')))
        _executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix='archive-job')
    return _executor


def _job_path(job_id: str) -> str:
    os.makedirs(JOBS_DIR, exist_ok=True)
    return os.path.join(JOBS_DIR, f'{job_id}.json')


def _persist(job: dict) -> None:
    try:
        with open(_job_path(job['id']), 'w', encoding='utf-8') as f:
            json.dump(job, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


def _calc_progress(phase: str, done: int, total: int, *, include_images: bool) -> int:
    if phase == 'done':
        return 100
    if phase == 'preparing':
        return 5
    if phase == 'coco':
        return 15 if include_images else 90
    if phase == 'images' and total > 0:
        return 15 + int(85 * done / total)
    if phase == 'images':
        return 15
    return 0


def _update(job_id: str, patch: dict) -> dict | None:
    with _lock:
        job = _jobs.get(job_id)
        if not job:
            return None
        job.update(patch)
        phase = job.get('phase') or ''
        job['phase_label'] = PHASE_LABELS.get(phase, phase)
        job['progress'] = _calc_progress(
            phase,
            int(job.get('done') or 0),
            int(job.get('total') or 0),
            include_images=bool(job.get('include_images')),
        )
        _jobs[job_id] = job
        _persist(job)
        return dict(job)


def init_archive_jobs(app) -> None:
    global _app, _product_name
    _app = app
    try:
        from server.core import PRODUCT_NAME
        _product_name = PRODUCT_NAME or _product_name
    except Exception:
        pass
    os.makedirs(JOBS_DIR, exist_ok=True)
    loaded = []
    try:
        for fn in os.listdir(JOBS_DIR):
            if not fn.endswith('.json'):
                continue
            path = os.path.join(JOBS_DIR, fn)
            try:
                with open(path, encoding='utf-8') as f:
                    job = json.load(f)
                if job.get('id'):
                    loaded.append(job)
            except (OSError, json.JSONDecodeError):
                continue
    except OSError:
        pass
    loaded.sort(key=lambda j: j.get('created_at') or 0, reverse=True)
    with _lock:
        for job in loaded[:MAX_JOBS]:
            if job.get('status') in ('pending', 'running'):
                job['status'] = 'failed'
                job['error'] = '服务已重启，归档任务已中断，请重新归档'
                job['finished_at'] = time.time()
                job['phase'] = 'failed'
                _persist(job)
            _jobs[job['id']] = job


def _load_task_query_meta(task_dir: str) -> dict:
    meta_path = os.path.join(task_dir, 'query_meta.json')
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _load_coco_for_archive(task_dir: str, selected_indices=None):
    csv_path = os.path.join(task_dir, 'result.csv')
    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        return None, []

    with open(coco_path, encoding='utf-8') as f:
        coco_data = json.load(f)

    query_meta = _load_task_query_meta(task_dir)
    if query_meta.get('data_source') == 'predict_result':
        from studio.export.pred_coco_layout import ensure_predict_annotations_for_export
        from server.core import get_effective_id2name
        coco_data = ensure_predict_annotations_for_export(
            coco_data, task_dir, id2name=get_effective_id2name(),
        )

    if not selected_indices:
        return coco_data, []

    selected_indices = {int(i) for i in selected_indices}
    filtered_images = [img for img in coco_data.get('images', []) if img.get('id') in selected_indices]
    selected_image_ids = {img['id'] for img in filtered_images}
    filtered_annotations = [
        ann for ann in coco_data.get('annotations', [])
        if ann.get('image_id') in selected_image_ids
    ]
    filtered_coco = {
        'images': filtered_images,
        'annotations': filtered_annotations,
        'categories': coco_data.get('categories', []),
    }
    if 'info' in coco_data:
        filtered_coco['info'] = coco_data['info']
    return filtered_coco, []


def _enrich_coco_archive_info(coco_data, query_meta, archived_at, include_images):
    base = build_coco_info(query_meta)
    info = {**base, **(coco_data.get('info') or {})}
    info.update({
        'description': info.get('description') or f'{_product_name} archive',
        'archived_at': archived_at,
        'include_images': include_images,
    })
    coco_data['info'] = {k: v for k, v in info.items() if v is not None and v != ''}
    return coco_data


def _validate_submit(task_id: str, data: dict, upload_folder: str) -> tuple[dict, str, str]:
    """同步校验，返回 (payload, task_dir, dest_dir)。"""
    archive_dir = (data.get('archive_dir') or '').strip()
    if not archive_dir:
        from server.core import load_config
        archive_dir = load_config().get('archive_base_path', '').strip()
    if not archive_dir:
        raise ValueError('请指定归档目录或在设置中配置 archive_base_path')

    archive_dir = os.path.abspath(os.path.expanduser(archive_dir))
    if not os.path.isdir(archive_dir):
        os.makedirs(archive_dir, exist_ok=True)

    task_dir = os.path.join(upload_folder, task_id)
    if not os.path.isdir(task_dir):
        raise ValueError('任务不存在')

    subfolder = (data.get('subfolder') or '').strip()
    if not subfolder:
        subfolder = f'archive_{task_id[:8]}_{stamp_compact()}'
    subfolder = re.sub(r'[^\w\-\u4e00-\u9fff]+', '_', subfolder).strip('_') or f'archive_{task_id[:8]}'
    dest_dir = os.path.join(archive_dir, subfolder)
    if os.path.exists(dest_dir):
        raise ValueError(f'目标目录已存在: {dest_dir}')

    indices = data.get('selected_indices')
    if indices is not None and len(indices) == 0:
        raise ValueError('未选中任何条目')

    coco_data, _ = _load_coco_for_archive(task_dir, indices if indices else None)
    if not coco_data:
        raise ValueError('COCO 标注文件不存在')

    query_meta = _load_task_query_meta(task_dir)
    if query_meta.get('data_source') == 'predict_result' and not (coco_data.get('annotations') or []):
        raise ValueError(
            '预测结果无可用标注框（ext 为空或类别均非缺陷检测标签）。请确认筛选后仍保留预测框。'
        )

    payload = {
        'task_id': task_id,
        'archive_dir': archive_dir,
        'subfolder': subfolder,
        'dest_dir': dest_dir,
        'selected_indices': indices,
        'include_images': bool(data.get('include_images', False)),
        'query_meta_patch': {
            k: data.get(k)
            for k in (
                'query_sql', 'python_code', 'start_time', 'end_time',
                'strategy_id', 'strategy_name', 'sample_size', 'query_sql_executed',
            )
            if data.get(k) not in (None, '')
        },
    }
    return payload, task_dir, dest_dir


def _run_archive_job(job_id: str, payload: dict) -> None:
    task_id = payload['task_id']
    task_dir = ''
    dest_dir = payload['dest_dir']
    include_images = payload['include_images']
    indices = payload.get('selected_indices')
    if indices is not None:
        indices = list(indices)

    _update(job_id, {
        'status': 'running',
        'started_at': time.time(),
        'phase': 'preparing',
        'message': '正在准备…',
        'done': 0,
        'total': 0,
    })

    try:
        if _app is None:
            raise RuntimeError('archive jobs 未初始化')
        with _app.app_context():
            upload_folder = _app.config['UPLOAD_FOLDER']
            task_dir = os.path.join(upload_folder, task_id)
            os.makedirs(dest_dir, exist_ok=True)

            coco_data, _ = _load_coco_for_archive(task_dir, indices if indices else None)
            if not coco_data:
                raise ValueError('COCO 标注文件不存在')

            query_meta = _load_task_query_meta(task_dir)
            for k, v in (payload.get('query_meta_patch') or {}).items():
                query_meta[k] = v

            _update(job_id, {'phase': 'coco', 'message': '写入 COCO…'})
            archived_at = format_iso_now()
            coco_data = _enrich_coco_archive_info(coco_data, query_meta, archived_at, include_images)
            coco_dest = os.path.join(dest_dir, '_annotations.coco.json')
            with open(coco_dest, 'w', encoding='utf-8') as f:
                json.dump(coco_data, f, ensure_ascii=False, indent=2)

            file_count = 1
            image_count = 0
            copy_skipped = 0

            if include_images:
                image_files = normalize_coco_images_for_task(
                    task_dir, coco_data, indices, for_export=True,
                )
                total = len(image_files)
                _update(job_id, {
                    'phase': 'images',
                    'total': total,
                    'done': 0,
                    'message': f'复制图片 0/{total}',
                })
                for i, (src, arc) in enumerate(image_files, 1):
                    dest = os.path.join(dest_dir, arc)
                    try:
                        os.makedirs(os.path.dirname(dest) or dest_dir, exist_ok=True)
                        shutil.copy2(src, dest)
                        image_count += 1
                    except OSError as copy_err:
                        copy_skipped += 1
                        print(f'⚠️ 归档复制跳过 ({i}/{total}) {src}: {copy_err}')
                    if i == total or i % 10 == 0:
                        _update(job_id, {
                            'done': i,
                            'message': f'复制图片 {i}/{total}',
                        })
                file_count += image_count
                if total and image_count == 0:
                    raise ValueError(
                        f'未能复制任何图片（共 {total} 条路径不可用或无权访问）',
                    )

            msg = '已归档 COCO 标注'
            if include_images:
                msg += f'及 {image_count} 张图片'
                if copy_skipped:
                    msg += f'（{copy_skipped} 张跳过）'

            _update(job_id, {
                'status': 'done',
                'phase': 'done',
                'finished_at': time.time(),
                'path': dest_dir,
                'file_count': file_count,
                'image_count': image_count,
                'copy_skipped': copy_skipped,
                'message': msg,
                'error': '',
                'progress': 100,
            })
    except Exception as e:  # noqa: BLE001
        _update(job_id, {
            'status': 'failed',
            'phase': 'failed',
            'finished_at': time.time(),
            'error': str(e),
            'message': str(e),
        })


def submit_archive_job(task_id: str, data: dict) -> dict:
    """提交后台归档，立即返回 job。"""
    if _app is None:
        raise RuntimeError('archive jobs 未初始化')
    with _app.app_context():
        payload, _task_dir, dest_dir = _validate_submit(
            task_id, data or {}, _app.config['UPLOAD_FOLDER'],
        )

    job_id = str(uuid.uuid4())
    now = time.time()
    job = {
        'id': job_id,
        'task_id': task_id,
        'status': 'pending',
        'phase': 'preparing',
        'phase_label': PHASE_LABELS['preparing'],
        'progress': 0,
        'done': 0,
        'total': 0,
        'message': '等待开始…',
        'created_at': now,
        'started_at': None,
        'finished_at': None,
        'path': '',
        'dest_dir': dest_dir,
        'include_images': payload['include_images'],
        'file_count': 0,
        'image_count': 0,
        'copy_skipped': 0,
        'error': '',
    }
    with _lock:
        _jobs[job_id] = job
        ids = sorted(_jobs.keys(), key=lambda i: _jobs[i].get('created_at') or 0, reverse=True)
        for old_id in ids[MAX_JOBS:]:
            _jobs.pop(old_id, None)
            try:
                os.remove(_job_path(old_id))
            except OSError:
                pass
        _persist(job)

    _ensure_executor().submit(_run_archive_job, job_id, payload)
    return dict(job)


def get_archive_job(job_id: str) -> dict | None:
    path = _job_path(job_id)
    disk = None
    if os.path.isfile(path):
        try:
            with open(path, encoding='utf-8') as f:
                disk = json.load(f)
        except (OSError, json.JSONDecodeError):
            disk = None
    with _lock:
        if disk:
            _jobs[job_id] = disk
            return dict(disk)
        job = _jobs.get(job_id)
        return dict(job) if job else None
