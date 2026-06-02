"""Magic-Fox 数据集增量同步：拉取标注 + 按需下载图片 + 可选写库。"""
import json
import logging
import os
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from studio.forge import forge_db
from studio.forge import forge_paths
from studio.forge import job_log
from studio.sync import magic_fox_bridge as mf
from studio.sync import magic_fox_fetch
from studio.sync import dataset_provenance
from studio.sync.magic_fox_discover import (
    build_data_view_url,
    build_snapshot_data_view_url,
    _subject_id_from_url,
)

logger = logging.getLogger('detforge.sync')

DEFAULT_BATCH_SIZE = 100
DEFAULT_HYDRATE_WORKERS = 8
DEFAULT_TIMEOUT = 120
DEFAULT_RETRIES = 2


def _is_permission_denied_error(exc: BaseException) -> bool:
    msg = str(exc or '').lower()
    return 'permission' in msg or '权限' in msg or 'not enough' in msg


def _fetch_dataset_meta_optional(base_url, token, source_id, flat, log_fn):
    """GET /datasets/{id}；部分账号仅有 dataset_items/page 权限时降级为空 meta。"""
    try:
        return flat['fetch_dataset_meta'](base_url, token, source_id)
    except RuntimeError as e:
        if _is_permission_denied_error(e):
            log_fn(
                f'警告: GET /datasets/{source_id} 无权限（{e}），'
                f'将仅用 dataset_items/page 继续同步'
            )
            return {}
        raise


def resolve_dataset_output_dir(project, dataset, config=None):
    """解析数据集本地绝对路径，并校验白名单。"""
    from server.core import load_config
    cfg = config or load_config()
    local_dir = str(dataset.get('local_dir') or '').strip()
    if os.path.isabs(local_dir):
        out = os.path.abspath(local_dir)
    else:
        root = str(project.get('local_root') or cfg.get('dataset_sync_root') or '').strip()
        if not root:
            root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'datasets')
        if not os.path.isabs(root):
            from studio.paths import PROJECT_ROOT
            root = os.path.join(PROJECT_ROOT, root)
        out = os.path.abspath(os.path.join(root, local_dir))
    if not forge_paths.is_within(out, forge_paths.allowed_sync_roots()):
        raise ValueError(f'同步目录不在允许范围内: {out}')
    os.makedirs(out, exist_ok=True)
    return out


def _count_local_images(out_dir, split_subdirs):
    n = 0
    exts = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
    if split_subdirs:
        for sub in ('train', 'valid', 'test'):
            d = os.path.join(out_dir, sub)
            if os.path.isdir(d):
                for fn in os.listdir(d):
                    if os.path.splitext(fn.lower())[1] in exts:
                        if os.path.isfile(os.path.join(d, fn)):
                            n += 1
    else:
        for fn in os.listdir(out_dir):
            p = os.path.join(out_dir, fn)
            if os.path.isfile(p) and os.path.splitext(fn.lower())[1] in exts:
                n += 1
    return n


def _annotation_box_count(item):
    anns = item.get('annotations') or []
    if not isinstance(anns, list):
        return 0
    total = 0
    for ann in anns:
        shapes = (ann or {}).get('shapes') or []
        total += len(shapes) if isinstance(shapes, list) else 0
    return total


def _parse_remote_mtime(item):
    for key in ('m_time', 'mtime', 'updated_at'):
        val = item.get(key)
        if val:
            return val
    return None


def _resolve_subject_id(project, dataset):
    for src in (
        dataset.get('data_view_url'),
        project.get('training_page_url'),
    ):
        sid = _subject_id_from_url(src)
        if sid is not None:
            return sid
    return None


def _backfill_data_view_url(project, dataset, source_type, source_id, detail_meta=None):
    if str(dataset.get('data_view_url') or '').strip():
        return
    approach_id = project.get('approach_id')
    if not approach_id:
        return
    subject_id = _resolve_subject_id(project, dataset)
    url = ''
    if source_type == 'dataset':
        url = build_data_view_url(int(approach_id), int(source_id), subject_id)
    elif source_type == 'snapshot' and detail_meta:
        base_ds = detail_meta.get('dataset_id')
        if base_ds:
            url = build_snapshot_data_view_url(
                int(approach_id), int(source_id), int(base_ds), subject_id,
            )
    if url:
        forge_db.upsert_sync_dataset({**dataset, 'data_view_url': url})


def sync_dataset(dataset_id, job_id=None, stop_check=None, on_progress=None, config=None, log_fn=None):
    """执行一次数据集同步，返回统计 dict。"""
    dataset = forge_db.get_sync_dataset(dataset_id)
    if not dataset:
        raise ValueError(f'数据集不存在: {dataset_id}')
    project = forge_db.get_sync_project(dataset['project_id'])
    if not project:
        raise ValueError(f'项目不存在: {dataset["project_id"]}')

    convert_to_coco, fetch_labels_map, generate_stats = mf.ensure_coco_export()
    flat = mf.ensure_flat_download_module()
    base_url, token = mf.get_api_token(config)

    out_dir = resolve_dataset_output_dir(project, dataset, config)
    source_type = str(dataset.get('source_type') or 'dataset')
    source_id = int(dataset['source_id'])
    strip_prefix = bool(dataset.get('strip_prefix', 1))
    use_split = bool(dataset.get('split_subdirs'))
    write_db = bool(dataset.get('write_db'))

    def _log(msg):
        if log_fn:
            log_fn(msg)
        logger.info(msg)

    _log(f'开始同步数据集 #{dataset_id}「{dataset.get("name")}」({source_type} #{source_id})')

    detail_for_approach = None
    if source_type == 'snapshot':
        _log(f'拉取训练快照 generate_id={source_id} …')
        detail_for_approach = flat['fetch_generate_detail'](base_url, token, source_id)
        detail_items = detail_for_approach.get('dataset_items') or []
        meta_count = detail_for_approach.get('count')
        if meta_count is not None and len(detail_items) < int(meta_count):
            _log(f'警告: 快照声明 {meta_count} 条，详情仅返回 {len(detail_items)} 条')
    else:
        _log(f'拉取底库 dataset_id={source_id} 全量列表 …')
        page_rows = magic_fox_fetch.fetch_dataset_items_all_pages(base_url, token, source_id)
        meta = _fetch_dataset_meta_optional(base_url, token, source_id, flat, _log)
        detail_items = flat['dataset_page_rows_to_detail_items'](page_rows)
        detail_for_approach = meta or None
        platform_count = int(meta.get('count') or meta.get('total_count') or 0)
        if platform_count:
            _log(f'平台 meta 数量={platform_count}，列表拉取={len(page_rows)} 条')
            if len(page_rows) < platform_count:
                raise RuntimeError(
                    f'底库 {source_id} 应共 {platform_count} 条，实际仅拉取 {len(page_rows)} 条，请检查 API 或重试'
                )
        else:
            _log(f'列表拉取={len(page_rows)} 条（未获取 datasets/{{id}} meta，以列表为准）')
        if not str(dataset.get('name') or '').strip() and meta.get('dataset_name'):
            forge_db.upsert_sync_dataset({**dataset, 'name': meta['dataset_name']})

    _backfill_data_view_url(project, dataset, source_type, source_id, detail_for_approach)

    if not detail_items:
        raise RuntimeError('线上数据集为空，无 dataset_items')

    remote_count = len(detail_items)
    _log(f'线上共 {remote_count} 条，开始拉取全量标注 …')
    _log('（标注拉取数据量大时可能耗时数分钟，请查看运行日志进度）')

    items = flat['hydrate_items_for_coco'](
        detail_items, base_url, token, DEFAULT_HYDRATE_WORKERS,
    )
    _log(f'标注合并完成 {len(items)}/{remote_count} 条')

    _log('正在生成 COCO 标注与 manifest …')

    approach_id = project.get('approach_id')
    if approach_id is None and detail_for_approach:
        raw = detail_for_approach.get('approach_id')
        if raw is not None:
            try:
                approach_id = int(raw)
            except (TypeError, ValueError):
                approach_id = None

    label_definitions = None
    if approach_id is not None:
        try:
            label_definitions = fetch_labels_map(int(approach_id), token)
        except Exception as e:  # noqa: BLE001
            logger.warning('拉取 labels 失败: %s', e)

    coco_data, category_stats = convert_to_coco(items, label_definitions)
    by_id: Dict[Any, Dict[str, Any]] = {}
    for it in items:
        iid = it.get('id')
        if iid is not None:
            by_id[iid] = it

    out = Path(out_dir)
    name_counts: Dict[str, Counter] = defaultdict(Counter)
    download_tasks: List[Tuple[str, Path]] = []
    manifest: List[Dict[str, Any]] = []
    pending_db_rows: List[Dict[str, Any]] = []
    skipped_images = 0
    provenance_inputs: List[Dict[str, Any]] = []

    for image in coco_data.get('images', []):
        if stop_check and stop_check():
            raise RuntimeError('同步已取消')
        iid = image.get('id')
        orig_fn = (image.get('file_name') or '').strip()
        item = by_id.get(iid)
        if not item or not orig_fn:
            continue
        key = (item.get('object_key') or '').strip()
        if not key:
            continue

        subdir = flat['split_type_to_subdir'](item.get('split_type')) if use_split else ''
        cnt = name_counts[subdir]

        if strip_prefix:
            stripped = flat['strip_export_filename'](orig_fn)
            final_fn = flat['assign_dedup_name'](stripped, cnt)
        else:
            final_fn = flat['assign_dedup_name'](orig_fn, cnt)

        if use_split:
            image['file_name'] = f'{subdir}/{final_fn}'
        else:
            image['file_name'] = final_fn

        dest = (out / subdir / final_fn) if use_split else (out / final_fn)
        local_path = str(dest)
        need_download = not (dest.exists() and dest.stat().st_size > 0)
        if need_download:
            download_tasks.append((key, dest))
        else:
            skipped_images += 1

        remote_item_id = item.get('dataset_item_id') or item.get('id')
        manifest.append({
            'remote_item_id': remote_item_id,
            'object_key': key,
            'file_name': final_fn,
            'coco_file_name': image['file_name'],
            'local_path': local_path,
            'skipped_download': not need_download,
        })
        if write_db and key:
            provenance_inputs.append({'object_key': key, 'file_name': final_fn})
            pending_db_rows.append({
                'remote_item_id': remote_item_id,
                'file_name': final_fn,
                'local_path': local_path,
                'object_key': key,
                'split_type': subdir or None,
                'annotations': item.get('annotations'),
                'box_count': _annotation_box_count(item),
                'remote_mtime': _parse_remote_mtime(item),
            })

    prov_list = []
    if write_db and provenance_inputs:
        try:
            prov_list = dataset_provenance.batch_lookup_provenance(provenance_inputs)
            hit = sum(
                1 for p in prov_list
                if p.get('trace_status') in ('matched', 'filename', 'fuzzy', 'sn_only')
            )
            _log(f'平台库溯源：{hit}/{len(provenance_inputs)} 条命中（精确 / 模糊 / SN）')
        except Exception as e:  # noqa: BLE001
            _log(f'警告: 平台库溯源失败（仍将写入样本）: {e}')
            prov_list = [{}] * len(pending_db_rows)

    if write_db and pending_db_rows:
        _log(f'写入 detforge 样本表 {len(pending_db_rows)} 条 …')
    for row, prov in zip(pending_db_rows, prov_list or [{}] * len(pending_db_rows)):
        if row.get('remote_item_id') is None:
            continue
        prov = prov or {}
        forge_db.upsert_dataset_item(
            dataset_id=int(dataset_id),
            remote_item_id=int(row['remote_item_id']),
            file_name=row['file_name'],
            local_path=row['local_path'],
            object_key=row['object_key'],
            split_type=row.get('split_type'),
            annotations=row.get('annotations'),
            box_count=row.get('box_count') or 0,
            remote_mtime=row.get('remote_mtime'),
            **{k: prov.get(k) for k in (
                'source_detail_id', 'product_no', 'product_id', 'product_type',
                'position', 'platform_c_time', 'trace_status',
            )},
        )

    ann_path = out / '_annotations.coco.json'
    ann_path.write_text(json.dumps(coco_data, ensure_ascii=False, indent=2), encoding='utf-8')
    stats = generate_stats(coco_data, category_stats)
    (out / 'stats.json').write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding='utf-8')
    (out / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    _log(f'COCO 已写入 {len(coco_data.get("images", []))} 张 · 标注框 {len(coco_data.get("annotations", []))} 个')

    downloaded_ok = 0
    downloaded_fail = 0
    if download_tasks:
        _log(f'待下载 {len(download_tasks)} 张（跳过已有 {skipped_images} 张）')

        def _download_progress(done, total, ok_count, fail_count):
            _log(f'下载进度 {done}/{total}（成功 {ok_count}，失败 {fail_count}）')

        downloaded_ok, downloaded_fail = flat['download_batches'](
            base_url, token, download_tasks,
            batch_size=DEFAULT_BATCH_SIZE,
            timeout_sec=DEFAULT_TIMEOUT,
            retries=DEFAULT_RETRIES,
            progress_fn=_download_progress,
        )
        _log(f'下载完成：成功 {downloaded_ok}，失败 {downloaded_fail}')
    else:
        _log(f'无需下载新图片（本地已有 {skipped_images} 张）')

    local_count = _count_local_images(out_dir, use_split)
    summary = {
        'dataset_id': int(dataset_id),
        'output_dir': out_dir,
        'remote_count': remote_count,
        'hydrated_count': len(items),
        'coco_images': len(coco_data.get('images', [])),
        'annotations_count': len(coco_data.get('annotations', [])),
        'download_ok': downloaded_ok,
        'download_fail': downloaded_fail,
        'skipped_existing': skipped_images,
        'local_count': local_count,
        'write_db': write_db,
    }

    if write_db:
        try:
            summary['trace_summary'] = forge_db.dataset_item_trace_summary(int(dataset_id))
        except Exception:  # noqa: BLE001
            pass

    err_msg = None
    if downloaded_fail:
        err_msg = f'{downloaded_fail} 张图片下载失败'

    forge_db.update_sync_dataset_stats(
        dataset_id,
        remote_count=remote_count,
        local_count=local_count,
        last_sync_job_id=job_id,
        last_sync_error=err_msg,
        last_sync_at=True,
    )

    if on_progress:
        on_progress()

    _log(
        f'同步完成：COCO {summary["coco_images"]} 张 · 标注框 {summary["annotations_count"]} · '
        f'本地 {local_count} 张 · 目录 {out_dir}'
    )

    if downloaded_fail and downloaded_ok == 0 and not skipped_images:
        raise RuntimeError(err_msg)
    return summary


def run_dataset_sync_job(job, stop_check=None, on_progress=None):
    """worker 入口：job.params.sync_dataset_id。"""
    params = job.get('params') or {}
    dataset_id = params.get('sync_dataset_id')
    if not dataset_id:
        raise ValueError('job.params.sync_dataset_id 缺失')
    job_id = job.get('id')

    def log_fn(msg):
        job_log.append(job_id, msg)

    items = forge_db.pending_items(job_id)
    item = items[0] if items else None
    if item:
        forge_db.mark_item_running(item['id'])
    try:
        log_fn(f'作业 #{job_id} 开始执行')
        summary = sync_dataset(
            int(dataset_id),
            job_id=job_id,
            stop_check=stop_check,
            on_progress=on_progress,
            log_fn=log_fn,
        )
        new_params = dict(params)
        new_params['result'] = summary
        import json as _json
        forge_db.update_job(job_id, params=_json.dumps(new_params, ensure_ascii=False))
        if item:
            forge_db.mark_item_done(item['id'], result_ref=int(dataset_id))
        forge_db.recompute_job_progress(job_id)
        return summary
    except Exception as e:
        job_log.append(job_id, f'同步失败: {e}')
        forge_db.update_sync_dataset_stats(int(dataset_id), last_sync_error=str(e), last_sync_at=True)
        if item:
            forge_db.mark_item_failed(item['id'], error=str(e))
        forge_db.recompute_job_progress(job_id)
        raise


def open_sync_dataset(dataset_id, config=None):
    """从已同步的数据集目录打开 COCO 看图会话。"""
    from studio import viz_bridge
    st = preview_sync_status(dataset_id, config)
    out_dir = st['output_dir']
    coco_path = os.path.join(out_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        raise FileNotFoundError('尚未生成 COCO 标注，请先执行一次同步')
    dataset = forge_db.get_sync_dataset(dataset_id)
    name = (dataset or {}).get('name') or f'sync-{dataset_id}'
    return viz_bridge.open_from_paths(coco_path, image_dir=out_dir, dataset_name=name)


def preview_sync_status(dataset_id, config=None):
    """对比本地/线上数量（不拉取）。"""
    dataset = forge_db.get_sync_dataset(dataset_id)
    if not dataset:
        raise ValueError(f'数据集不存在: {dataset_id}')
    project = forge_db.get_sync_project(dataset['project_id'])
    out_dir = resolve_dataset_output_dir(project, dataset, config)
    local_count = _count_local_images(out_dir, bool(dataset.get('split_subdirs')))
    db_count = forge_db.count_dataset_items(dataset_id) if dataset.get('write_db') else 0
    trace_summary = forge_db.dataset_item_trace_summary(dataset_id) if dataset.get('write_db') else None
    has_coco = os.path.isfile(os.path.join(out_dir, '_annotations.coco.json'))
    return {
        'dataset_id': int(dataset_id),
        'output_dir': out_dir,
        'remote_count': int(dataset.get('remote_count') or 0),
        'local_count': local_count,
        'db_item_count': db_count,
        'trace_summary': trace_summary,
        'has_coco': has_coco,
        'last_sync_at': dataset.get('last_sync_at'),
        'last_sync_error': dataset.get('last_sync_error'),
    }
