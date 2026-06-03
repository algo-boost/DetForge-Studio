"""筛选批次业务：从查询 task 创建批次、出站包、回传 manifest、归档与训练交接。"""
from __future__ import annotations

import csv
import io
import json
import os
import shutil
import uuid
from datetime import datetime

import pandas as pd

from studio.forge import forge_db
from studio.forge import forge_paths
from studio.paths import PROJECT_ROOT as BASE_DIR
from studio.curation.dispositions import (
    DISP_NG_CONFIRMED,
    INTENT_DAILY_NG,
    INTENT_LABELS,
    INTENT_REPLAY_EVAL,
    parse_image_disposition,
)
from studio.curation.handoff_pack import assemble_handoff_dir, handoff_inbox_root

MANIFEST_FIELDS = [
    'batch_row_id', 'img_name', 'product_no', 'product_type', 'check_status',
    'categories', 'disposition', 'need_platform_label', 'source_task_id',
    'decision', 'reject_reason', 'note',
]

README_EXPORT = """# 筛选批次出站包

## 外部筛选（改 COCO JSON）
1. 用 COCOVisualizer / 自研工具打开 `_annotations.coco.json`
2. 删除不要的图片条目（及对应 annotations），或改标注
3. 保留的 images 即为筛选结果
4. 回到 DefectLoop Studio → 筛选归档 → 上传筛选后的 `_annotations.coco.json`

## 出站包内容
- `_annotations.coco.json` — 主要编辑对象
- `images/` — 图片副本
- `manifest.csv` — 只读索引（可选对照，不必改）
- `provenance.json` — 血缘信息

系统按 COCO 中 `images[].file_name` 与批次对齐：在 COCO 里的 → 保留，不在的 → 剔除。
"""


def _now():
    from studio.timezone_util import format_now
    return format_now()


def _task_dir(task_id):
    from flask import current_app
    return os.path.join(current_app.config['UPLOAD_FOLDER'], str(task_id))


def curation_root():
    return os.path.join(BASE_DIR, 'exports', 'curation')


def batch_export_dir(batch_code):
    return os.path.join(curation_root(), str(batch_code))


def handoff_root():
    return handoff_inbox_root()


def infer_intent_type(strategy_id=None, data_source=None, explicit=None):
    if explicit:
        return explicit
    sid = str(strategy_id or '').lower()
    ds = str(data_source or '').lower()
    if 'replay' in sid or 'eval' in sid or ds in ('predict_result', 'predict'):
        return INTENT_REPLAY_EVAL
    return INTENT_DAILY_NG


def normalize_decision(raw):
    """将外部填写的 decision 规范为 keep/reject/pending。"""
    if raw is None:
        return 'pending'
    s = str(raw).strip().lower()
    if not s:
        return 'pending'
    if s in ('keep', '保留', 'k', '1', 'y', 'yes', 'true', '是'):
        return 'keep'
    if s in ('reject', '剔除', '删除', 'r', '0', 'n', 'no', 'false', '否'):
        return 'reject'
    return 'pending'


def categories_from_row(row):
    """从 CSV 行或 ext 提取缺陷类别摘要。"""
    ext = row.get('ext')
    if isinstance(ext, str) and ext.strip():
        try:
            ext = json.loads(ext)
        except (TypeError, ValueError):
            ext = None
    if isinstance(ext, dict):
        preds = ext.get('original_predictions') or []
        names = []
        for p in preds:
            if isinstance(p, dict):
                n = p.get('name') or p.get('category')
                if n:
                    names.append(str(n))
        if names:
            return ','.join(sorted(set(names))[:8])
    ann = row.get('annotations')
    if isinstance(ann, str) and ann.strip():
        try:
            ann = json.loads(ann)
        except (TypeError, ValueError):
            ann = None
    if isinstance(ann, list):
        names = [str(a.get('category') or a.get('name') or '') for a in ann if isinstance(a, dict)]
        names = [n for n in names if n]
        if names:
            return ','.join(sorted(set(names))[:8])
    return ''


def parse_import_csv(text):
    """解析回传的 manifest CSV，返回 {batch_row_id|None, img_name, decision, reject_reason, note} 列表。"""
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError('CSV 无表头')
    rows = []
    for row in reader:
        rid = (row.get('batch_row_id') or row.get('batch_rowId') or '').strip()
        img = (row.get('img_name') or row.get('filename') or row.get('file_name') or '').strip()
        decision = normalize_decision(row.get('decision') or row.get('keep'))
        reason = (row.get('reject_reason') or row.get('reason') or '').strip() or None
        note = (row.get('note') or row.get('备注') or '').strip() or None
        if not rid and not img:
            continue
        if decision == 'pending':
            continue
        rows.append({
            'batch_row_id': rid or None,
            'img_name': img or None,
            'decision': decision,
            'reject_reason': reason,
            'note': note,
        })
    if not rows:
        raise ValueError('CSV 中未找到有效的 decision（keep/reject）')
    return rows


def merge_import_decisions(batch_id, import_rows):
    """将回传行合并到批次条目，返回 {matched, unmatched_import, still_pending}。"""
    items = forge_db.list_curation_items(batch_id, limit=100000)
    by_row_id = {str(i['batch_row_id']): i for i in items}
    by_img = {}
    for i in items:
        name = str(i.get('img_name') or '').strip().lower()
        if name:
            by_img[name] = i

    matched = 0
    unmatched = []
    for imp in import_rows:
        item = None
        if imp.get('batch_row_id'):
            item = by_row_id.get(str(imp['batch_row_id']))
        if not item and imp.get('img_name'):
            item = by_img.get(str(imp['img_name']).strip().lower())
        if not item:
            unmatched.append(imp)
            continue
        forge_db.update_curation_item_decision(
            batch_id, item['batch_row_id'], imp['decision'],
            reject_reason=imp.get('reject_reason'), note=imp.get('note'),
        )
        matched += 1

    counts = forge_db.recompute_curation_counts(batch_id)
    return {'matched': matched, 'unmatched_import': unmatched, **counts}


def parse_coco_data(raw):
    """解析 COCO JSON 字符串或 dict。"""
    if isinstance(raw, dict):
        coco = raw
    elif isinstance(raw, str):
        coco = json.loads(raw)
    else:
        raise ValueError('无效 COCO 数据')
    if not isinstance(coco.get('images'), list):
        raise ValueError('无效 COCO：缺少 images 数组')
    return coco


def coco_keep_file_names(coco):
    """从 COCO 提取保留的图片 file_name（小写）集合。"""
    names = set()
    for img in coco.get('images', []):
        if not isinstance(img, dict):
            continue
        fn = str(img.get('file_name') or img.get('filename') or '').strip()
        if fn:
            names.add(fn.lower())
    return names


def coco_image_disposition_map(coco, default=DISP_NG_CONFIRMED):
    """file_name(lower) → (disposition, need_platform_label)。"""
    out = {}
    for img in coco.get('images', []):
        if not isinstance(img, dict):
            continue
        fn = str(img.get('file_name') or img.get('filename') or '').strip()
        if not fn:
            continue
        disp, nl = parse_image_disposition(img, default=default)
        out[fn.lower()] = (disp, nl)
    return out


def merge_import_coco(batch_id, coco, save_dir=None):
    """用筛选后的 COCO 更新批次：images 内 → keep，其余 → reject；并保存 COCO 文件。"""
    keep_names = coco_keep_file_names(coco)
    if not keep_names:
        raise ValueError('COCO 中无有效 images.file_name')

    disp_map = coco_image_disposition_map(coco)
    items = forge_db.list_curation_items(batch_id, limit=100000)
    by_img = {}
    for i in items:
        name = str(i.get('img_name') or '').strip().lower()
        if name:
            by_img[name] = i

    matched_keep = 0
    for it in items:
        name = str(it.get('img_name') or '').strip().lower()
        if name and name in keep_names:
            disp, nl = disp_map.get(name, (DISP_NG_CONFIRMED, False))
            forge_db.update_curation_item_decision(
                batch_id, it['batch_row_id'], 'keep',
                disposition=disp, need_platform_label=nl,
            )
            matched_keep += 1
        else:
            forge_db.update_curation_item_decision(
                batch_id, it['batch_row_id'], 'reject',
                reject_reason='not_in_curated_coco',
                disposition='rejected', need_platform_label=False,
            )

    if matched_keep == 0:
        raise ValueError('COCO 中的图片与批次无匹配（请检查 file_name 是否与 img_name 一致）')

    batch = forge_db.get_curation_batch(batch_id)
    out_dir = save_dir or batch.get('export_dir') or batch_export_dir(batch['batch_code'])
    os.makedirs(out_dir, exist_ok=True)
    coco_path = os.path.join(out_dir, '_annotations.coco.json')
    with open(coco_path, 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)

    counts = forge_db.recompute_curation_counts(batch_id)
    unmatched_coco = sorted(keep_names - set(by_img.keys()))
    return {
        'matched_keep': matched_keep,
        'coco_path': coco_path,
        'coco_image_count': len(keep_names),
        'unmatched_coco_names': unmatched_coco[:20],
        'unmatched_coco_count': len(unmatched_coco),
        **counts,
    }


def _curated_coco_path(batch):
    """优先使用回传的筛选 COCO，否则回落到来源 task。"""
    if batch.get('export_dir'):
        p = os.path.join(batch['export_dir'], '_annotations.coco.json')
        if os.path.isfile(p) and batch.get('status') in ('imported', 'archived', 'handoff_ready', 'handoff_done', 'closed'):
            return p
    task_dir = _task_dir(batch['source_task_id'])
    p = os.path.join(task_dir, '_annotations.coco.json')
    return p if os.path.isfile(p) else None


def import_coco(batch_id, coco_raw):
    """上传筛选后的 COCO JSON。"""
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    if batch.get('status') not in ('created', 'exported', 'imported'):
        raise ValueError(f"当前状态 {batch.get('status')} 不允许导入")

    coco = parse_coco_data(coco_raw)
    result = merge_import_coco(batch_id, coco)
    forge_db.update_curation_batch(
        batch_id,
        status='imported',
        imported_at=_now(),
        export_dir=os.path.dirname(result['coco_path']),
    )
    result['batch'] = forge_db.get_curation_batch(batch_id)
    return result


def import_filter_result(batch_id, file_text, filename=''):
    """按文件名自动选择 COCO 或 manifest CSV。"""
    name = (filename or '').lower()
    if name.endswith('.json') or file_text.lstrip().startswith('{'):
        return import_coco(batch_id, file_text)
    return import_manifest(batch_id, file_text)


def _load_query_meta(task_dir):
    meta_path = os.path.join(task_dir, 'query_meta.json')
    if os.path.isfile(meta_path):
        with open(meta_path, encoding='utf-8') as f:
            return json.load(f)
    return {}


def _make_batch_code():
    from studio.timezone_util import stamp_compact
    stamp = stamp_compact()
    short = uuid.uuid4().hex[:6]
    return f'cb_{stamp}_{short}'


def create_from_task(task_id, strategy_id=None, strategy_name=None, reviewer=None, note=None,
                     data_source=None, intent_type=None):
    """从查询 task 创建筛选批次（仅写库，尚未出站）。"""
    if not forge_db.schema_ready():
        raise RuntimeError('detforge 写库未初始化，请先在设置或 POST /api/forge/schema/init 建表')

    task_dir = _task_dir(task_id)
    if not os.path.isdir(task_dir):
        raise ValueError(f'查询任务不存在: {task_id}')

    csv_path = os.path.join(task_dir, 'result.csv')
    if not os.path.isfile(csv_path):
        raise ValueError('任务缺少 result.csv')

    meta = _load_query_meta(task_dir)
    ds = data_source or meta.get('data_source') or 'detail'
    batch_code = _make_batch_code()
    intent = infer_intent_type(strategy_id or meta.get('strategy_id'), ds, intent_type)

    df = pd.read_csv(csv_path, encoding='utf-8')
    if df.empty:
        raise ValueError('查询结果为空，无法创建筛选批次')

    batch_id = forge_db.insert_curation_batch({
        'batch_code': batch_code,
        'source_task_id': str(task_id),
        'strategy_id': strategy_id or meta.get('strategy_id'),
        'strategy_name': strategy_name or meta.get('strategy_name'),
        'data_source': ds,
        'intent_type': intent,
        'reviewer': reviewer,
        'note': note,
        'total_count': len(df),
        'pending_count': len(df),
    })

    item_rows = []
    for seq, (_, row) in enumerate(df.iterrows()):
        img_path = row.get('img_path', '')
        if pd.isna(img_path):
            img_path = ''
        img_name = os.path.basename(str(img_path)) if img_path else ''
        batch_row_id = f'{batch_code}-r{seq + 1:05d}'
        item_rows.append({
            'batch_id': batch_id,
            'batch_row_id': batch_row_id,
            'seq': seq,
            'img_name': img_name,
            'img_path': str(img_path) if img_path else None,
            'product_no': str(row.get('product_no') or '') if pd.notna(row.get('product_no')) else None,
            'product_type': str(row.get('product_type') or '') if pd.notna(row.get('product_type')) else None,
            'check_status': str(row.get('check_status') or '') if pd.notna(row.get('check_status')) else None,
            'categories_summary': categories_from_row(row),
            'decision': 'pending',
            'source_meta': {
                'row_index': int(seq),
                'c_time': str(row.get('c_time') or '') if pd.notna(row.get('c_time')) else None,
            },
        })
    forge_db.insert_curation_items_batch(item_rows)

    return forge_db.get_curation_batch(batch_id)


def _write_manifest(batch, items, dest_path):
    with open(dest_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        for it in items:
            writer.writerow({
                'batch_row_id': it['batch_row_id'],
                'img_name': it.get('img_name') or '',
                'product_no': it.get('product_no') or '',
                'product_type': it.get('product_type') or '',
                'check_status': it.get('check_status') or '',
                'categories': it.get('categories_summary') or '',
                'disposition': it.get('disposition') or '',
                'need_platform_label': 1 if it.get('need_platform_label') else 0,
                'source_task_id': batch['source_task_id'],
                'decision': it.get('decision') or '',
                'reject_reason': it.get('reject_reason') or '',
                'note': it.get('note') or '',
            })


def _write_provenance(batch, dest_path, extra=None):
    payload = {
        'batch_code': batch['batch_code'],
        'batch_id': batch['id'],
        'purpose': 'external_curation',
        'source': {
            'task_id': batch['source_task_id'],
            'strategy_id': batch.get('strategy_id'),
            'strategy_name': batch.get('strategy_name'),
            'data_source': batch.get('data_source'),
        },
        'counts': {
            'total': batch.get('total_count'),
            'keep': batch.get('keep_count'),
            'reject': batch.get('reject_count'),
            'pending': batch.get('pending_count'),
        },
        'exported_at': _now(),
    }
    if extra:
        payload.update(extra)
    with open(dest_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def export_batch(batch_id, include_images=True):
    """生成出站包：manifest + COCO + 图片 + provenance + README。"""
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')

    items = forge_db.list_curation_items(batch_id, limit=100000)
    if not items:
        raise ValueError('批次无条目')

    out_dir = batch_export_dir(batch['batch_code'])
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    images_dir = os.path.join(out_dir, 'images')
    if include_images:
        os.makedirs(images_dir, exist_ok=True)

    task_dir = _task_dir(batch['source_task_id'])
    coco_src = os.path.join(task_dir, '_annotations.coco.json')
    if os.path.isfile(coco_src):
        shutil.copy2(coco_src, os.path.join(out_dir, '_annotations.coco.json'))

    copied = 0
    for it in items:
        src = it.get('img_path')
        if include_images and src and os.path.isfile(src):
            dst = os.path.join(images_dir, it.get('img_name') or os.path.basename(src))
            if not os.path.isfile(dst):
                try:
                    shutil.copy2(src, dst)
                    copied += 1
                except OSError:
                    pass
        elif include_images and it.get('img_name'):
            alt = os.path.join(task_dir, it['img_name'])
            if os.path.isfile(alt):
                try:
                    shutil.copy2(alt, os.path.join(images_dir, it['img_name']))
                    copied += 1
                except OSError:
                    pass

    _write_manifest(batch, items, os.path.join(out_dir, 'manifest.csv'))
    _write_provenance(batch, os.path.join(out_dir, 'provenance.json'))
    with open(os.path.join(out_dir, 'README.txt'), 'w', encoding='utf-8') as f:
        f.write(README_EXPORT)

    forge_db.update_curation_batch(
        batch_id,
        status='exported',
        export_dir=out_dir,
        exported_at=_now(),
    )
    return {
        'out_dir': out_dir,
        'batch_code': batch['batch_code'],
        'items': len(items),
        'images_copied': copied,
    }


def import_manifest(batch_id, csv_text):
    """上传筛选结果 manifest。"""
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    if batch.get('status') not in ('created', 'exported', 'imported'):
        raise ValueError(f"当前状态 {batch.get('status')} 不允许导入")

    rows = parse_import_csv(csv_text)
    result = merge_import_decisions(batch_id, rows)
    forge_db.update_curation_batch(batch_id, status='imported', imported_at=_now())
    result['batch'] = forge_db.get_curation_batch(batch_id)
    return result


def _copy_item_image(it, batch, task_dir, images_dir):
    """复制单条保留样本图片，返回是否成功。"""
    name = it.get('img_name')
    src = it.get('img_path')
    if src and os.path.isfile(src):
        shutil.copy2(src, os.path.join(images_dir, name or os.path.basename(src)))
        return True
    if name and os.path.isfile(os.path.join(task_dir, name)):
        shutil.copy2(os.path.join(task_dir, name), os.path.join(images_dir, name))
        return True
    export_dir = batch.get('export_dir') or ''
    if name and export_dir:
        alt = os.path.join(export_dir, 'images', name)
        if os.path.isfile(alt):
            shutil.copy2(alt, os.path.join(images_dir, name))
            return True
    return False


def _write_curated_coco_to(dest_dir, batch, keep_items, task_dir):
    """写入归档/交接目录的 COCO：优先用回传的筛选 COCO。"""
    curated = _curated_coco_path(batch)
    if curated and os.path.isfile(curated):
        shutil.copy2(curated, os.path.join(dest_dir, '_annotations.coco.json'))
        return
    coco_src = os.path.join(task_dir, '_annotations.coco.json')
    if os.path.isfile(coco_src) and keep_items:
        keep_names = [i.get('img_name') for i in keep_items if i.get('img_name')]
        filtered = _filter_coco_keep(coco_src, keep_names)
        with open(os.path.join(dest_dir, '_annotations.coco.json'), 'w', encoding='utf-8') as f:
            json.dump(filtered, f, ensure_ascii=False, indent=2)


def _filter_coco_keep(coco_path, keep_names):
    with open(coco_path, encoding='utf-8') as f:
        coco = json.load(f)
    keep_set = {n.lower() for n in keep_names if n}
    filtered_images = []
    for img in coco.get('images', []):
        fn = str(img.get('file_name') or '')
        if fn.lower() in keep_set:
            filtered_images.append(img)
    image_ids = {img['id'] for img in filtered_images}
    filtered_ann = [a for a in coco.get('annotations', []) if a.get('image_id') in image_ids]
    return {
        'info': coco.get('info') or {},
        'images': filtered_images,
        'annotations': filtered_ann,
        'categories': coco.get('categories', []),
    }


def archive_batch(batch_id, archive_dir=None, copy_images=True, treat_pending_as='reject'):
    """确认归档：可选复制保留图到 archive_dir。"""
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    if batch.get('status') not in ('imported', 'exported'):
        raise ValueError('请先上传筛选后的 COCO JSON 再归档')

    items = forge_db.list_curation_items(batch_id, limit=100000)
    pending = [i for i in items if (i.get('decision') or 'pending') == 'pending']
    if pending and treat_pending_as in ('reject', 'keep'):
        for it in pending:
            forge_db.update_curation_item_decision(
                batch_id, it['batch_row_id'], treat_pending_as,
                reject_reason='auto_pending' if treat_pending_as == 'reject' else None,
            )
        forge_db.recompute_curation_counts(batch_id)
        batch = forge_db.get_curation_batch(batch_id)
        items = forge_db.list_curation_items(batch_id, limit=100000)
    elif pending:
        raise ValueError(f'仍有 {len(pending)} 条未标注 decision，请补全或选择自动处理 pending')

    from server.core import load_config
    cfg = load_config()
    if not archive_dir:
        base = str(cfg.get('archive_base_path') or '').strip()
        if base:
            parent = os.path.abspath(os.path.expanduser(base))
        else:
            parent = os.path.join(BASE_DIR, 'exports', 'curation_archives')
    else:
        parent = os.path.abspath(os.path.expanduser(str(archive_dir)))
    archive_dir = os.path.join(parent, batch['batch_code'])

    if not forge_paths.safe_export_dir(archive_dir):
        raise ValueError('归档目录不在允许范围内（exports/ 或 manual_qc_export_roots）')

    os.makedirs(archive_dir, exist_ok=True)
    images_dir = os.path.join(archive_dir, 'images')
    if copy_images:
        os.makedirs(images_dir, exist_ok=True)

    keep_items = [i for i in items if i.get('decision') == 'keep']
    copied = 0
    task_dir = _task_dir(batch['source_task_id'])

    if copy_images:
        for it in keep_items:
            if _copy_item_image(it, batch, task_dir, images_dir):
                copied += 1

    _write_manifest(batch, keep_items, os.path.join(archive_dir, 'manifest_kept.csv'))
    _write_provenance(batch, os.path.join(archive_dir, 'provenance.json'), {
        'purpose': 'archived_curation',
        'archived_at': _now(),
        'keep_count': len(keep_items),
    })
    _write_curated_coco_to(archive_dir, batch, keep_items, task_dir)

    forge_db.update_curation_batch(
        batch_id,
        status='archived',
        archive_dir=archive_dir,
        archived_at=_now(),
    )
    return {
        'archive_dir': archive_dir,
        'keep_count': len(keep_items),
        'images_copied': copied,
        'batch': forge_db.get_curation_batch(batch_id),
    }


def _build_handoff_subset(batch, items, task_dir, sub_dir, label_filter=None):
    """写入 handoff 子目录；label_filter='need_label' 时仅待打标样本。"""
    if label_filter == 'need_label':
        subset = [i for i in items if i.get('need_platform_label')]
    else:
        subset = list(items)
    if not subset:
        return None

    out_dir = sub_dir
    os.makedirs(out_dir, exist_ok=True)
    images_dir = os.path.join(out_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    copied = 0
    for it in subset:
        if _copy_item_image(it, batch, task_dir, images_dir):
            copied += 1

    _write_curated_coco_to(out_dir, batch, subset, task_dir)
    _write_manifest(batch, subset, os.path.join(out_dir, 'manifest.csv'))
    _write_provenance(batch, os.path.join(out_dir, 'provenance.json'), {
        'purpose': 'training_handoff',
        'handoff_at': _now(),
        'subset': label_filter or 'all_kept',
        'record_count': len(subset),
    })
    intent = batch.get('intent_type') or INTENT_DAILY_NG
    with open(os.path.join(out_dir, 'HANDOFF.md'), 'w', encoding='utf-8') as f:
        f.write(
            f"# 训练交接包 — {label_filter or 'all_kept'}\n\n"
            f"- 场景：{INTENT_LABELS.get(intent, intent)}\n"
            f"- 批次：`{batch['batch_code']}`\n"
            f"- 样本数：{len(subset)}\n"
            f"- 目录：`{out_dir}`\n"
        )
    return {'out_dir': out_dir, 'keep_count': len(subset), 'images_copied': copied}


def generate_handoff(batch_id, handoff_note=None, split='both'):
    """生成训练交接包（keep 样本；可按 need_label 分包）。

    split: 'both' | 'all' | 'need_label'
    """
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    if batch.get('status') not in ('archived', 'imported'):
        raise ValueError('请先完成归档再生成交接包')

    items = forge_db.list_curation_items(batch_id, decision='keep', limit=100000)
    if not items:
        raise ValueError('无保留样本，无法生成交接包')

    task_dir = _task_dir(batch['source_task_id'])
    base_dir = os.path.join(handoff_root(), batch['batch_code'])
    if os.path.exists(base_dir):
        shutil.rmtree(base_dir)
    os.makedirs(base_dir, exist_ok=True)

    packs = {}
    if split in ('both', 'all'):
        r = _build_handoff_subset(batch, items, task_dir, os.path.join(base_dir, 'all_kept'))
        if r:
            packs['all_kept'] = r
    if split in ('both', 'need_label'):
        r = _build_handoff_subset(
            batch, items, task_dir, os.path.join(base_dir, 'to_label'), label_filter='need_label',
        )
        if r:
            packs['to_label'] = r

    if not packs:
        raise ValueError('无符合分包条件的样本（to_label 为空时可改用 split=all）')

    if handoff_note:
        with open(os.path.join(base_dir, 'HANDOFF.md'), 'w', encoding='utf-8') as f:
            f.write(f"# 训练交接包\n\n{batch['batch_code']}\n\n{handoff_note}\n")

    if not forge_paths.safe_sync_dir(base_dir) and not forge_paths.safe_export_dir(base_dir):
        raise ValueError('交接目录不在允许路径内')

    forge_db.update_curation_batch(
        batch_id,
        status='handoff_ready',
        handoff_dir=base_dir,
        handoff_at=_now(),
    )
    total_copied = sum(p.get('images_copied', 0) for p in packs.values())
    return {
        'handoff_dir': base_dir,
        'packs': packs,
        'keep_count': len(items),
        'images_copied': total_copied,
        'batch': forge_db.get_curation_batch(batch_id),
    }


def list_archive_handoff(limit=50):
    """统一筛选归档列表：批次 + 人工质检汇总。"""
    batches = forge_db.list_curation_batches(limit=limit)
    for b in batches:
        b['record_type'] = 'curation'
        intent = b.get('intent_type') or INTENT_DAILY_NG
        b['intent_label'] = INTENT_LABELS.get(intent, intent)
    qc_summary = forge_db.manual_qc_training_summary()
    return {
        'curation_batches': batches,
        'manual_qc_summary': qc_summary,
        'total_curation': len(batches),
    }


def mark_handoff_done(batch_id, sync_dataset_id=None, note=None):
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    fields = {'status': 'closed' if sync_dataset_id else 'handoff_done'}
    if sync_dataset_id:
        fields['sync_dataset_id'] = int(sync_dataset_id)
    if note:
        fields['note'] = (batch.get('note') or '') + '\n' + note
    forge_db.update_curation_batch(batch_id, **fields)
    return forge_db.get_curation_batch(batch_id)


def delete_batch(batch_id):
    """删除筛选批次及其条目（仅数据库记录，不删磁盘目录）。"""
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError('批次不存在')
    forge_db.delete_curation_items_by_batch(batch_id)
    forge_db.delete_curation_batch(batch_id)
    return {
        'id': int(batch_id),
        'batch_code': batch.get('batch_code'),
    }
