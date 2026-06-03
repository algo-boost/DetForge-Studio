"""人工质检归档：按客户 SN 到平台 vision_backend.product_detection_detail_result
查找对应缺陷图记录，人工选中匹配图并标注缺陷类型/成像情况后写入 detforge.manual_qc。
支持按时段 + 类别查询导出图片到指定目录。
"""
import csv
import os
import re
import shutil
import uuid
from datetime import datetime

from studio.forge import forge_db

from studio.paths import PROJECT_ROOT as BASE_DIR
from studio.curation.dispositions import (
    INTENT_CUSTOMER_QC,
    TRAINING_HANDOFF_READY,
    disposition_from_qc_record,
)
from studio.curation.handoff_pack import (
    assemble_handoff_dir,
    build_coco_from_manual_qc_records,
    handoff_inbox_root,
)

# 可配置类别（持久化在 config.json）
DEFAULT_IMAGING_CATEGORIES = ['成像清晰', '成像不清', '拍不到']
DEFAULT_DEFECT_TYPES = ['脏污', '划伤', '焊丝', '线头', '异色', '胶水', '压痕', '破损']
_CFG_IMAGING_KEY = 'manual_qc_imaging_categories'
_CFG_DEFECT_KEY = 'manual_qc_defect_types'
_CFG_STRICT_KEY = 'manual_qc_defect_strict'


def default_daily_batch_id(when=None):
    """每日一批：默认 batch_id = YYYY-MM-DD（配置时区）。"""
    from studio.timezone_util import format_datetime, now_local
    dt = when or now_local()
    return format_datetime(dt, '%Y-%m-%d')


def resolve_batch_id(batch_id=None):
    """未指定批次时使用当日批次。"""
    bid = str(batch_id or '').strip()
    return bid or default_daily_batch_id()


# ── 类别配置 ───────────────────────────────────────────────────────

def get_categories():
    from server.core import load_config
    cfg = load_config()
    imaging = cfg.get(_CFG_IMAGING_KEY) or DEFAULT_IMAGING_CATEGORIES
    defects = cfg.get(_CFG_DEFECT_KEY) or DEFAULT_DEFECT_TYPES
    return {
        'imaging_categories': [str(x) for x in imaging if str(x).strip()],
        'defect_types': [str(x) for x in defects if str(x).strip()],
        'defect_strict': bool(cfg.get(_CFG_STRICT_KEY, False)),
    }


def save_categories(imaging_categories=None, defect_types=None, defect_strict=None):
    from server.core import load_config, save_config
    cfg = load_config()
    if imaging_categories is not None:
        cfg[_CFG_IMAGING_KEY] = [str(x).strip() for x in imaging_categories if str(x).strip()]
    if defect_types is not None:
        cfg[_CFG_DEFECT_KEY] = [str(x).strip() for x in defect_types if str(x).strip()]
    if defect_strict is not None:
        cfg[_CFG_STRICT_KEY] = bool(defect_strict)
    save_config(cfg)
    return get_categories()


# ── 平台缺陷图查找 ─────────────────────────────────────────────────

def _img_path_from_object_key(object_key):
    from server.core import load_config, DEFAULT_CONFIG
    if not object_key:
        return ''
    config = load_config()
    base = str(config.get('img_base_path') or DEFAULT_CONFIG['img_base_path'] or '').strip()
    if base and not base.endswith(('/', '\\')):
        base += '/'
    return base + str(object_key)


def _normalize_existing_path(path):
    """返回磁盘上真实存在的路径；Windows 上尝试 E:/D: 盘符互换。"""
    path = str(path or '').strip()
    if not path:
        return ''
    if os.path.isfile(path):
        return path
    if os.name == 'nt' and len(path) >= 2 and path[1] == ':':
        drive = path[0].upper()
        rest = path[2:].lstrip('\\/')
        for alt_drive in ('E', 'D', 'C'):
            if alt_drive == drive:
                continue
            alt = f'{alt_drive}:/{rest}'.replace('/', '\\')
            if os.path.isfile(alt):
                return alt
    return path


def _resolve_detail_img_path(row):
    """解析平台明细图绝对路径：优先 local_pic_url 原路径，其次 origin_object_key 拼接。"""
    row = dict(row or {})
    local_pic = str(row.get('local_pic_url') or '').strip()
    if local_pic:
        path = _normalize_existing_path(local_pic.replace('\\', '/'))
        if path:
            return path

    ok = str(row.get('origin_object_key') or '').strip()
    if ok:
        path = _normalize_existing_path(_img_path_from_object_key(ok))
        if path:
            return path

    return local_pic or _img_path_from_object_key(ok) or ''


_DETAIL_SELECT = """
    SELECT d.id, d.product_no, d.origin_object_key, d.local_pic_url, d.ext, d.c_time,
           d.check_status, d.detection_result_status,
           r.product_type AS product_type
    FROM product_detection_detail_result d
    LEFT JOIN (
        SELECT product_no, MAX(product_type) AS product_type
        FROM product_detection_result GROUP BY product_no
    ) r ON d.product_no = r.product_no
"""


def find_platform_records_by_sn(sn, limit=50):
    """按 SN 查平台明细缺陷记录（含款型 product_type），用于展示该 SN 全部图。"""
    from server.core import get_db_client
    sn = str(sn or '').strip()
    if not sn:
        return []
    client = get_db_client()
    sql = _DETAIL_SELECT + " WHERE d.product_no = %s ORDER BY d.id DESC LIMIT %s"
    try:
        rows = client.fetchall(sql, (sn, int(limit)))
    except Exception:
        rows = []
    for row in rows:
        row['img_path'] = _resolve_detail_img_path(row)
    return rows


def _fetch_detail_record(detail_id):
    from server.core import get_db_client
    client = get_db_client()
    sql = _DETAIL_SELECT + " WHERE d.id = %s LIMIT 1"
    try:
        row = client.fetchone(sql, (int(detail_id),))
    except Exception:
        row = None
    if row:
        row['img_path'] = _resolve_detail_img_path(row)
    return row or {}


def _match_status(records):
    if not records:
        return 'not_found'
    if len(records) > 1:
        return 'multiple'
    return 'matched'


# ── 归档 ───────────────────────────────────────────────────────────

def _validate_defect_type(defect_type):
    """严格模式下缺陷类型必须在配置列表内。"""
    if not defect_type:
        return
    cats = get_categories()
    if cats.get('defect_strict'):
        allowed = cats.get('defect_types') or []
        if str(defect_type).strip() not in allowed:
            raise ValueError(f'缺陷类型不在配置列表内: {defect_type}')


def archive_one(product_no, customer_img_path=None, batch_id=None, note=None,
                position=None, defect_type=None, qc_category=None,
                matched_detail_id=None, no_match=False, limit=50, force=False):
    """归档一条人工质检记录。

    三种匹配方式：
    - matched_detail_id 指定 → 用人工选中的那条平台记录；
    - no_match=True → 标记未匹配（如「拍不到」），不写匹配图；
    - 否则按 SN 自动取最新一条（批量/快速归档）。
    force=True 时允许重复 SN+客户图归档（否则硬拦截）。
    """
    _validate_defect_type(defect_type)
    batch_id = resolve_batch_id(batch_id)
    duplicate = forge_db.find_manual_qc_duplicate(product_no, customer_img_path)
    if duplicate and not force:
        raise ValueError(
            f'该 SN+客户图已归档 #{duplicate["id"]}（{duplicate.get("qc_category") or ""}），'
            f'如需重复请勾选「强制归档」'
        )

    if matched_detail_id:
        best = _fetch_detail_record(matched_detail_id)
        status = 'matched' if best else 'not_found'
        candidate_count = 1 if best else 0
    elif no_match:
        best, status, candidate_count = {}, 'not_found', 0
    else:
        records = find_platform_records_by_sn(product_no, limit=limit)
        status = _match_status(records)
        best = records[0] if records else {}
        candidate_count = len(records)

    row = {
        'batch_id': batch_id,
        'product_no': str(product_no or '').strip(),
        'customer_img_path': customer_img_path,
        'matched_detail_id': best.get('id'),
        'matched_img_path': best.get('img_path'),
        'matched_object_key': best.get('origin_object_key'),
        'defect_info': {'ext': best.get('ext')} if best.get('ext') else None,
        'defect_type': defect_type,
        'qc_category': qc_category,
        'product_type': best.get('product_type'),
        'position': position,
        'match_status': status,
        'note': note,
        'training_status': 'pending',
    }
    row['disposition'] = disposition_from_qc_record(row)
    try:
        qc_id = forge_db.insert_manual_qc(row)
    except Exception as e:  # noqa: BLE001
        if 'Duplicate' in str(e) or 'duplicate' in str(e).lower():
            raise ValueError('该 SN+客户图已存在归档记录（数据库唯一约束）') from e
        raise
    return {
        'id': qc_id,
        'product_no': row['product_no'],
        'match_status': status,
        'qc_category': qc_category,
        'defect_type': defect_type,
        'matched_detail_id': row['matched_detail_id'],
        'matched_img_path': row['matched_img_path'],
        'candidate_count': candidate_count,
        'duplicate_of': duplicate['id'] if duplicate else None,
        'batch_id': batch_id,
    }


def archive_batch(entries, batch_id=None):
    """批量归档：entries=[{product_no, customer_img_path?, note?, defect_type?, qc_category?,
    matched_detail_id?, no_match?}]。"""
    batch_id = resolve_batch_id(batch_id)
    results = []
    for entry in entries or []:
        results.append(archive_one(
            product_no=entry.get('product_no'),
            customer_img_path=entry.get('customer_img_path'),
            batch_id=batch_id,
            note=entry.get('note'),
            position=entry.get('position'),
            defect_type=entry.get('defect_type'),
            qc_category=entry.get('qc_category'),
            matched_detail_id=entry.get('matched_detail_id'),
            no_match=bool(entry.get('no_match')),
            force=bool(entry.get('force')),
        ))
    summary = {
        'total': len(results),
        'matched': sum(1 for r in results if r['match_status'] == 'matched'),
        'not_found': sum(1 for r in results if r['match_status'] == 'not_found'),
        'multiple': sum(1 for r in results if r['match_status'] == 'multiple'),
    }
    return {'batch_id': batch_id, 'results': results, 'summary': summary}


def get_workflow_summary():
    """归档库概览：训练交接状态 + 交接收件箱路径。"""
    summary = forge_db.manual_qc_training_summary()
    summary['daily_batch_id'] = default_daily_batch_id()
    summary['handoff_inbox_root'] = handoff_inbox_root()
    summary['export_default_root'] = os.path.join(BASE_DIR, 'exports', 'manual_qc_export')
    return summary


def list_batch_groups(limit=60):
    """按 batch_id（缺省按归档日期）汇总批次。"""
    return forge_db.list_manual_qc_batch_groups(limit=limit)


# ── 导出 ───────────────────────────────────────────────────────────

def _safe_name(text, fallback='未分类'):
    s = re.sub(r'[\\/:*?"<>|]+', '_', str(text or '').strip())
    return s or fallback


def export_records(start=None, end=None, categories=None, defect_types=None,
                   out_dir=None, include='both', limit=None, as_zip=False):
    """按时段 + 类别导出图片到目录。

    include: 'platform'（匹配到的平台缺陷图）/ 'customer'（客户图）/ 'both'。
    目录结构：<out_dir>/<成像类别>/<SN>__<id>__platform|customer.<ext>，并写 manifest.csv。
    as_zip=True 时额外打包为 zip，结果含 zip_path 供下载。
    """
    from studio.forge import forge_paths
    rows = forge_db.list_manual_qc(
        start=start, end=end, categories=categories, defect_types=defect_types,
        limit=limit or 1000000,
    )
    if not out_dir:
        from studio.timezone_util import stamp_compact
        stamp = stamp_compact()
        out_dir = os.path.join(BASE_DIR, 'exports', 'manual_qc_export', stamp)
    out_dir = os.path.abspath(out_dir)
    # 安全：导出目录必须落在白名单根目录内（默认 exports/）
    if not forge_paths.safe_export_dir(out_dir):
        raise ValueError('导出目录不在允许范围内（默认仅允许 exports/ 下，可经 manual_qc_export_roots 配置扩展）')
    os.makedirs(out_dir, exist_ok=True)

    copied, missing = 0, 0
    manifest = []
    for r in rows:
        cat_dir = os.path.join(out_dir, _safe_name(r.get('qc_category')))
        sn = _safe_name(r.get('product_no'), fallback='SN')
        rid = r.get('id')
        record = {
            'id': rid, 'product_no': r.get('product_no'),
            'qc_category': r.get('qc_category'), 'defect_type': r.get('defect_type'),
            'product_type': r.get('product_type'), 'match_status': r.get('match_status'),
            'archived_at': r.get('archived_at'), 'note': r.get('note'),
            'exported_platform': '', 'exported_customer': '',
        }
        targets = []
        if include in ('both', 'platform') and r.get('matched_img_path'):
            targets.append(('platform', r['matched_img_path']))
        if include in ('both', 'customer') and r.get('customer_img_path'):
            targets.append(('customer', r['customer_img_path']))
        for kind, src in targets:
            if not src or not os.path.exists(src):
                missing += 1
                continue
            ext = os.path.splitext(src)[1] or '.jpg'
            dst_name = f"{sn}__{rid}__{kind}{ext}"
            os.makedirs(cat_dir, exist_ok=True)
            try:
                shutil.copy2(src, os.path.join(cat_dir, dst_name))
                copied += 1
                record[f'exported_{kind}'] = os.path.join(_safe_name(r.get('qc_category')), dst_name)
            except Exception:
                missing += 1
        manifest.append(record)

    manifest_path = os.path.join(out_dir, 'manifest.csv')
    if manifest:
        with open(manifest_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
            writer.writeheader()
            writer.writerows(manifest)

    result = {
        'out_dir': out_dir,
        'records': len(rows),
        'copied': copied,
        'missing': missing,
        'manifest': manifest_path if manifest else None,
    }
    if as_zip:
        zip_base = out_dir.rstrip('/\\')
        zip_path = shutil.make_archive(zip_base, 'zip', root_dir=out_dir)
        result['zip_path'] = zip_path
    return result


def generate_training_handoff(start=None, end=None, categories=None, batch_id=None,
                              training_status='pending', note=None):
    """人工质检 → 标准训练交接包（COCO + images + manifest + provenance）。"""
    from studio.forge import forge_paths

    rows = forge_db.list_manual_qc(
        batch_id=batch_id, start=start, end=end, categories=categories,
        training_status=training_status, limit=100000,
    )
    rows = [r for r in rows if r.get('matched_img_path')]
    if not rows:
        raise ValueError('无可用平台匹配图，无法生成交接包')

    from studio.timezone_util import stamp_compact
    stamp = stamp_compact()
    run_code = f'qc_{stamp}_{uuid.uuid4().hex[:6]}'
    out_dir = os.path.join(handoff_inbox_root(), run_code)

    coco = build_coco_from_manual_qc_records(rows)

    def copy_images(images_dir):
        copied = 0
        for r in rows:
            src = r.get('matched_img_path')
            if not src or not os.path.isfile(src):
                continue
            fname = os.path.basename(str(src))
            dst = os.path.join(images_dir, fname)
            if not os.path.isfile(dst):
                shutil.copy2(src, dst)
                copied += 1
        return copied

    manifest_rows = []
    for r in rows:
        fname = os.path.basename(str(r.get('matched_img_path') or ''))
        disp = disposition_from_qc_record(r)
        manifest_rows.append({
            'file_name': fname,
            'product_no': r.get('product_no'),
            'disposition': disp,
            'need_platform_label': 1 if disp in ('need_label', 'fn_missed', 'fp_model') else 0,
            'qc_category': r.get('qc_category'),
            'defect_type': r.get('defect_type'),
            'manual_qc_id': r.get('id'),
            'source': 'manual_qc',
        })

    result = assemble_handoff_dir(
        out_dir,
        intent_type=INTENT_CUSTOMER_QC,
        coco_data=coco,
        image_copy_fn=copy_images,
        manifest_rows=manifest_rows,
        provenance_extra={
            'run_code': run_code,
            'record_count': len(rows),
            'batch_id': batch_id,
            'filters': {'start': start, 'end': end, 'categories': categories},
        },
        readme_lines=[
            f'- 场景：人工质检',
            f'- 运行码：`{run_code}`',
            f'- 样本数：{len(rows)}',
            f'- 目录：`{out_dir}`',
            note or '',
        ],
    )

    if not forge_paths.safe_sync_dir(out_dir) and not forge_paths.safe_export_dir(out_dir):
        raise ValueError('交接目录不在允许路径内')

    qc_ids = [r['id'] for r in rows]
    forge_db.update_manual_qc_training_batch(
        qc_ids, TRAINING_HANDOFF_READY, handoff_dir=out_dir,
    )
    result['run_code'] = run_code
    result['record_count'] = len(rows)
    result['qc_ids'] = qc_ids
    return result


# ── 维护：清理未被引用的客户图 ─────────────────────────────────────

def cleanup_orphan_uploads(dry_run=True, root=None):
    """删除 uploads/manual_qc/ 下未被任何 manual_qc 记录引用的图片。

    dry_run=True 仅返回待清理列表，不实际删除。root 可覆盖扫描根目录（测试用）。
    """
    upload_root = root or os.path.join(BASE_DIR, 'uploads', 'manual_qc')
    if not os.path.isdir(upload_root):
        return {'scanned': 0, 'orphans': [], 'deleted': 0, 'dry_run': dry_run}
    referenced = {os.path.abspath(p) for p in forge_db.referenced_customer_imgs()}
    orphans, scanned = [], 0
    for root, _, files in os.walk(upload_root):
        for fn in files:
            scanned += 1
            ap = os.path.abspath(os.path.join(root, fn))
            if ap not in referenced:
                orphans.append(ap)
    deleted = 0
    if not dry_run:
        for p in orphans:
            try:
                os.remove(p)
                deleted += 1
            except OSError:
                pass
    return {'scanned': scanned, 'orphans': orphans, 'deleted': deleted, 'dry_run': dry_run}
