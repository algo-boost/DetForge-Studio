"""人工质检归档：按客户 SN 到平台 vision_backend.product_detection_detail_result
查找对应缺陷图记录，人工选中匹配图并标注缺陷类型/成像情况后写入 detforge.manual_qc。
支持按时段 + 类别查询导出图片到指定目录。
"""
import csv
import json
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
DEFAULT_IMAGING_CATEGORIES = ['未拍到', '成像不清', '检出', '漏检']
DEFAULT_DEFECT_TYPES = ['脏污', '划伤', '焊丝', '线头', '异色', '胶水', '压痕', '破损']
_CFG_IMAGING_KEY = 'manual_qc_imaging_categories'
_CFG_DEFECT_KEY = 'manual_qc_defect_types'
_CFG_STRICT_KEY = 'manual_qc_defect_strict'
_CFG_ARCHIVE_ROOT_KEY = 'manual_qc_archive_root'
_CFG_ARCHIVE_AUTO_KEY = 'manual_qc_archive_auto_sync'
_CFG_ARCHIVE_INCLUDE_KEY = 'manual_qc_archive_include'


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


WORKFLOW_INTAKE = 'intake'
WORKFLOW_CONFIRMED = 'confirmed'
WORKFLOW_ARCHIVED = 'archived'
WORKFLOW_VOID = 'void'


def _now_str():
    from studio.timezone_util import format_now
    return format_now()


def enrich_platform_record(record):
    """为平台明细补充 annotations / box_count，供核对台画框。"""
    from studio.export.annotation_parser import parse_row_predictions
    row = dict(record or {})
    preds = parse_row_predictions(row)
    anns = [{
        'bbox': p.get('bbox'),
        'category': p.get('name') or '',
        'score': p.get('confidence', 0),
    } for p in preds if p.get('bbox')]
    row['annotations'] = anns
    row['box_count'] = len(anns)
    return row


def enrich_platform_records(records):
    return [enrich_platform_record(r) for r in (records or [])]


def record_to_view_item(record):
    """转为前端 DetailImageStage 可用的 item。"""
    r = enrich_platform_record(record)
    return {
        'id': r.get('id'),
        'img_path': r.get('img_path') or '',
        'img_name': os.path.basename(str(r.get('img_path') or '')),
        'check_status': str(r.get('check_status') or ''),
        'detection_result_status': str(r.get('detection_result_status') or ''),
        'product_type': r.get('product_type'),
        'annotations': r.get('annotations') or [],
        'box_count': r.get('box_count') or 0,
        'c_time': str(r.get('c_time') or ''),
    }


def intake_one(product_no, customer_img_path=None, batch_id=None, note=None,
               defect_type=None, source=None, external_ref=None, force=False):
    """登记入队（不匹配平台图）。"""
    product_no = str(product_no or '').strip()
    if not product_no:
        raise ValueError('product_no 不能为空')
    batch_id = resolve_batch_id(batch_id)
    if customer_img_path:
        dup = forge_db.find_manual_qc_duplicate(
            product_no, customer_img_path, workflow_status=[WORKFLOW_INTAKE, WORKFLOW_CONFIRMED],
        )
        if dup and not force:
            raise ValueError(f'该 SN+客户图已在队列中 #{dup["id"]}（{dup.get("workflow_status")}）')
        archived = forge_db.find_manual_qc_duplicate(product_no, customer_img_path)
        if archived and not force:
            raise ValueError(
                f'该 SN+客户图已归档 #{archived["id"]}（{archived.get("qc_category") or ""}）'
            )
    row = {
        'batch_id': batch_id,
        'product_no': product_no,
        'customer_img_path': customer_img_path,
        'defect_type': defect_type or None,
        'note': note,
        'match_status': 'pending',
        'workflow_status': WORKFLOW_INTAKE,
        'source': source or 'ui',
        'external_ref': external_ref,
        'intake_at': _now_str(),
        'archived_at': None,
        'training_status': 'pending',
    }
    qc_id = forge_db.insert_manual_qc(row)
    return {'id': qc_id, 'product_no': product_no, 'batch_id': batch_id, 'workflow_status': WORKFLOW_INTAKE}


def intake_batch(entries, batch_id=None, source=None):
    """批量登记。返回 created / skipped / errors。"""
    batch_id = resolve_batch_id(batch_id)
    created, skipped, errors = [], [], []
    for i, entry in enumerate(entries or []):
        try:
            ext_ref = entry.get('external_ref')
            if ext_ref:
                existing = forge_db.list_manual_qc(
                    limit=1, workflow_status=[WORKFLOW_INTAKE, WORKFLOW_CONFIRMED, WORKFLOW_ARCHIVED],
                )
                # external_ref lookup - simple query via list not ideal; skip for now use duplicate check
            res = intake_one(
                product_no=entry.get('product_no'),
                customer_img_path=entry.get('customer_img_path'),
                batch_id=entry.get('batch_id') or batch_id,
                note=entry.get('note'),
                defect_type=entry.get('defect_type'),
                source=entry.get('source') or source or 'api',
                external_ref=ext_ref,
                force=bool(entry.get('force')),
            )
            created.append(res)
        except ValueError as e:
            if entry.get('skip_on_duplicate'):
                skipped.append({'index': i, 'error': str(e), 'entry': entry})
            else:
                errors.append({'index': i, 'error': str(e), 'entry': entry})
        except Exception as e:  # noqa: BLE001
            errors.append({'index': i, 'error': str(e), 'entry': entry})
    return {
        'batch_id': batch_id,
        'created': created,
        'skipped': skipped,
        'errors': errors,
        'summary': {'total': len(entries or []), 'created': len(created), 'skipped': len(skipped), 'errors': len(errors)},
    }


def _apply_match_fields(row, *, matched_detail_id=None, no_match=False):
    """根据选中平台记录或无匹配，写入匹配字段。"""
    if no_match:
        row['matched_detail_id'] = None
        row['matched_img_path'] = None
        row['matched_object_key'] = None
        row['defect_info'] = None
        row['match_status'] = 'not_found'
        row['product_type'] = row.get('product_type')
        return row
    if not matched_detail_id:
        return row
    best = _fetch_detail_record(matched_detail_id)
    if not best:
        raise ValueError(f'平台记录不存在: id={matched_detail_id}')
    row['matched_detail_id'] = best.get('id')
    row['matched_img_path'] = best.get('img_path')
    row['matched_object_key'] = best.get('origin_object_key')
    row['defect_info'] = {'ext': best.get('ext')} if best.get('ext') else None
    row['product_type'] = best.get('product_type')
    row['match_status'] = 'matched'
    return row


def save_review(qc_id, *, matched_detail_id=None, no_match=False,
                qc_category=None, defect_type=None, note=None,
                mark_confirmed=True):
    """核对暂存：写入匹配与分类，默认 status=confirmed。"""
    rec = forge_db.get_manual_qc(qc_id)
    if not rec:
        raise ValueError(f'案卷不存在: {qc_id}')
    if rec.get('workflow_status') == WORKFLOW_ARCHIVED:
        raise ValueError('已定案记录不可修改')
    if rec.get('workflow_status') == WORKFLOW_VOID:
        raise ValueError('案卷已作废')
    if not qc_category:
        raise ValueError('请选择成像情况')
    _validate_defect_type(defect_type)
    if not no_match and not matched_detail_id:
        raise ValueError('请选择匹配平台图或标记无匹配')
    fields = {
        'qc_category': qc_category,
        'defect_type': defect_type or None,
        'note': note if note is not None else rec.get('note'),
        'workflow_status': WORKFLOW_CONFIRMED if mark_confirmed else rec.get('workflow_status'),
    }
    match_row = _apply_match_fields(
        dict(rec), matched_detail_id=matched_detail_id, no_match=no_match,
    )
    for k in ('matched_detail_id', 'matched_img_path', 'matched_object_key',
              'defect_info', 'match_status', 'product_type'):
        fields[k] = match_row.get(k)
    fields['disposition'] = disposition_from_qc_record({**rec, **fields})
    forge_db.update_manual_qc(qc_id, fields)
    return forge_db.get_manual_qc(qc_id)


def confirm_one(qc_id, *, matched_detail_id=None, no_match=False,
                qc_category=None, defect_type=None, note=None, force=False):
    """单条确认归档（可从 intake 一步完成，或 confirmed 定案）。"""
    rec = forge_db.get_manual_qc(qc_id)
    if not rec:
        raise ValueError(f'案卷不存在: {qc_id}')
    st = rec.get('workflow_status')
    if st == WORKFLOW_ARCHIVED:
        raise ValueError('已归档')
    if st == WORKFLOW_VOID:
        raise ValueError('案卷已作废')

    has_review_input = (
        qc_category is not None or defect_type is not None or note is not None
        or matched_detail_id is not None or no_match
    )
    if st == WORKFLOW_INTAKE or (st == WORKFLOW_CONFIRMED and has_review_input):
        cat = qc_category or rec.get('qc_category')
        if not cat:
            raise ValueError('请选择成像情况')
        mid = matched_detail_id if matched_detail_id is not None else rec.get('matched_detail_id')
        nm = bool(no_match)
        if not nm and not mid:
            raise ValueError('请选择匹配平台图或标记无匹配')
        save_review(
            qc_id,
            matched_detail_id=mid,
            no_match=nm,
            qc_category=cat,
            defect_type=defect_type if defect_type is not None else rec.get('defect_type'),
            note=note if note is not None else rec.get('note'),
        )
    elif st != WORKFLOW_CONFIRMED:
        raise ValueError('请先完成核对')

    rec = forge_db.get_manual_qc(qc_id)
    if not rec.get('qc_category'):
        raise ValueError('请选择成像情况')
    if rec.get('match_status') != 'not_found' and not rec.get('matched_detail_id'):
        raise ValueError('请选择匹配平台图或标记无匹配')

    duplicate = forge_db.find_manual_qc_duplicate(rec.get('product_no'), rec.get('customer_img_path'))
    if duplicate and int(duplicate['id']) != int(qc_id) and not force:
        raise ValueError(
            f'该 SN+客户图已归档 #{duplicate["id"]}，如需重复请 force=true'
        )

    forge_db.update_manual_qc(qc_id, {
        'workflow_status': WORKFLOW_ARCHIVED,
        'archived_at': _now_str(),
        'disposition': disposition_from_qc_record(rec),
    })
    out = forge_db.get_manual_qc(qc_id)
    result = {
        'id': qc_id,
        'product_no': out.get('product_no'),
        'match_status': out.get('match_status'),
        'qc_category': out.get('qc_category'),
        'defect_type': out.get('defect_type'),
        'matched_detail_id': out.get('matched_detail_id'),
        'batch_id': out.get('batch_id'),
        'workflow_status': WORKFLOW_ARCHIVED,
        'duplicate_of': duplicate['id'] if duplicate and int(duplicate['id']) != int(qc_id) else None,
    }
    try:
        sync_info = sync_record_to_archive_root(rec=out)
        if sync_info:
            result['archive_sync'] = sync_info
    except Exception as exc:  # noqa: BLE001
        result['archive_sync_error'] = str(exc)
    return result


def confirm_batch(ids=None, entries=None, force=False):
    """批量确认归档。entries 可含 review 字段一步完成。"""
    results, errors = [], []
    if entries:
        items = entries
    else:
        items = [{'id': i} for i in (ids or [])]
    for item in items:
        qid = item.get('id')
        try:
            results.append(confirm_one(
                qid,
                matched_detail_id=item.get('matched_detail_id'),
                no_match=bool(item.get('no_match')),
                qc_category=item.get('qc_category'),
                defect_type=item.get('defect_type'),
                note=item.get('note'),
                force=force or bool(item.get('force')),
            ))
        except Exception as e:  # noqa: BLE001
            errors.append({'id': qid, 'error': str(e)})
    return {
        'results': results,
        'errors': errors,
        'summary': {'total': len(items), 'archived': len(results), 'errors': len(errors)},
    }


_HISTORY_TRACK_FIELDS = (
    'qc_category', 'defect_type', 'note', 'matched_detail_id',
    'matched_img_path', 'match_status', 'disposition', 'product_type',
)


def _history_snapshot(rec):
    if not rec:
        return {}
    return {k: rec.get(k) for k in _HISTORY_TRACK_FIELDS}


def _diff_snapshots(before, after):
    changed = {}
    for k in _HISTORY_TRACK_FIELDS:
        bv, av = before.get(k), after.get(k)
        if bv != av:
            changed[k] = {'from': bv, 'to': av}
    return changed


def update_archived_record(qc_id, *, matched_detail_id=None, no_match=False,
                           qc_category=None, defect_type=None, note=None,
                           operator=None, comment=None):
    """修订已定案记录（与核对台相同字段），写入变更历史。"""
    rec = forge_db.get_manual_qc(qc_id)
    if not rec:
        raise ValueError(f'记录不存在: {qc_id}')
    if rec.get('workflow_status') != WORKFLOW_ARCHIVED:
        raise ValueError('仅已定案记录可在此修订')
    cat = qc_category if qc_category is not None else rec.get('qc_category')
    if not cat:
        raise ValueError('请选择成像情况')
    dt = defect_type if defect_type is not None else rec.get('defect_type')
    _validate_defect_type(dt)
    nm = bool(no_match)
    mid = matched_detail_id if matched_detail_id is not None else rec.get('matched_detail_id')
    if not nm and not mid:
        raise ValueError('请选择匹配平台图或标记无匹配')

    before = _history_snapshot(rec)
    fields = {
        'qc_category': cat,
        'defect_type': dt or None,
        'note': note if note is not None else rec.get('note'),
    }
    match_row = _apply_match_fields(
        dict(rec), matched_detail_id=mid, no_match=nm,
    )
    for k in ('matched_detail_id', 'matched_img_path', 'matched_object_key',
              'defect_info', 'match_status', 'product_type'):
        fields[k] = match_row.get(k)
    fields['disposition'] = disposition_from_qc_record({**rec, **fields})
    forge_db.update_manual_qc(qc_id, fields)
    updated = forge_db.get_manual_qc(qc_id)
    after = _history_snapshot(updated)
    changed = _diff_snapshots(before, after)
    history_id = None
    if changed:
        history_id = forge_db.insert_manual_qc_history(
            qc_id,
            change_type='revise',
            operator=operator,
            comment=comment,
            snapshot_before=before,
            snapshot_after=after,
            changed_fields=changed,
        )
    try:
        settings = get_archive_settings()
        if settings.get('archive_root_resolved'):
            sync_record_to_archive_root(rec=updated, force=True)
    except Exception:
        pass
    return {'record': updated, 'history_id': history_id, 'changed_fields': changed}


def list_record_history(qc_id, limit=100):
    return forge_db.list_manual_qc_history(qc_id, limit=limit)


def void_records(ids, reason=None):
    """作废案卷（intake/confirmed）。"""
    n = 0
    for qid in ids or []:
        rec = forge_db.get_manual_qc(qid)
        if not rec or rec.get('workflow_status') == WORKFLOW_ARCHIVED:
            continue
        note = rec.get('note') or ''
        if reason:
            note = f'{note}\n[void] {reason}'.strip()
        forge_db.update_manual_qc(qid, {
            'workflow_status': WORKFLOW_VOID,
            'note': note or None,
        })
        n += 1
    return {'voided': n}


# ── 归档（兼容旧 API：直接定案） ───────────────────────────────────

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
        'workflow_status': WORKFLOW_ARCHIVED,
        'archived_at': _now_str(),
        'intake_at': _now_str(),
        'source': 'legacy',
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


def build_platform_sn_coco(records):
    """将 SN 候选平台明细转为 COCO（file_name 用绝对路径，供样本图库打开）。"""
    from studio.export.csv2coco import build_coco_info

    images = []
    annotations = []
    cat_map = {}
    ann_id = 1
    for r in enrich_platform_records(records or []):
        img_id = int(r.get('id') or 0)
        path = str(r.get('img_path') or '').strip()
        if not img_id or not path:
            continue
        images.append({
            'id': img_id,
            'file_name': os.path.abspath(path),
            'product_no': r.get('product_no'),
            'product_type': r.get('product_type'),
        })
        for ann in r.get('annotations') or []:
            bbox = ann.get('bbox')
            if not bbox or len(bbox) < 4:
                continue
            cat_name = str(ann.get('category') or 'defect').strip() or 'defect'
            if cat_name not in cat_map:
                cat_map[cat_name] = len(cat_map) + 1
            cid = cat_map[cat_name]
            row = {
                'id': ann_id,
                'image_id': img_id,
                'category_id': cid,
                'bbox': bbox,
                'iscrowd': 0,
                'area': float(bbox[2]) * float(bbox[3]),
            }
            if ann.get('score') is not None:
                row['score'] = float(ann['score'])
            annotations.append(row)
            ann_id += 1
    categories = [{'id': cid, 'name': name} for name, cid in sorted(cat_map.items(), key=lambda x: x[1])]
    return {
        'info': build_coco_info({'purpose': 'manual_qc_sn_lookup'}),
        'images': images,
        'annotations': annotations,
        'categories': categories,
    }


def open_viz_session_for_sn(sn, limit=100):
    """为当前 SN 平台候选图创建样本图库会话（完整看图工具能力）。"""
    import tempfile
    from studio import viz_bridge

    sn = str(sn or '').strip()
    if not sn:
        raise ValueError('product_no 不能为空')
    records = find_platform_records_by_sn(sn, limit=int(limit))
    records = enrich_platform_records(records)
    if not records:
        raise ValueError(f'未找到 SN={sn} 的平台图')
    coco = build_platform_sn_coco(records)
    if not coco.get('images'):
        raise ValueError('候选图无有效本地路径，无法打开样本图库')
    from studio.paths import app_temp_dir

    tmp = tempfile.mkdtemp(prefix='mqc_viz_', dir=app_temp_dir())
    coco_path = os.path.join(tmp, '_annotations.coco.json')
    with open(coco_path, 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)
    safe_sn = re.sub(r'[^\w\-]+', '_', sn)[:48]
    return viz_bridge.open_from_paths(
        coco_path, image_dir=tmp, dataset_name=f'mqc-{safe_sn}',
    )


def get_workflow_summary():
    """归档库概览：训练交接 + 工作流队列计数。"""
    summary = forge_db.manual_qc_training_summary()
    wf = forge_db.manual_qc_workflow_counts()
    summary['workflow'] = wf
    summary['intake_count'] = wf.get('intake', 0)
    summary['confirmed_count'] = wf.get('confirmed', 0)
    summary['daily_batch_id'] = default_daily_batch_id()
    summary['handoff_inbox_root'] = handoff_inbox_root()
    summary['export_default_root'] = os.path.join(BASE_DIR, 'exports', 'manual_qc_export')
    arch = get_archive_settings()
    summary['archive_root'] = arch.get('archive_root') or ''
    summary['archive_root_resolved'] = arch.get('archive_root_resolved') or ''
    summary['archive_auto_sync'] = bool(arch.get('auto_sync'))
    summary['archive_include'] = arch.get('include') or 'both'
    return summary


def list_batch_groups(limit=60):
    """按 batch_id（缺省按归档日期）汇总批次。"""
    return forge_db.list_manual_qc_batch_groups(limit=limit)


# ── 归档目录配置与导出 ─────────────────────────────────────────────

def _safe_name(text, fallback='未分类'):
    s = re.sub(r'[\\/:*?"<>|]+', '_', str(text or '').strip())
    return s or fallback


def _archive_date_prefix(archived_at):
    """从 archived_at 解析 YYYY/MM/DD；缺省用当天。"""
    if archived_at:
        s = str(archived_at).strip()
        if len(s) >= 10:
            ymd = s[:10].replace('/', '-')
            parts = ymd.split('-')
            if len(parts) == 3 and all(parts):
                return f"{parts[0]}/{parts[1]}/{parts[2]}"
    from datetime import datetime
    now = datetime.now()
    return f"{now.year}/{now.month:02d}/{now.day:02d}"


def resolve_archive_root():
    from server.core import load_config
    cfg = load_config()
    raw = str(cfg.get(_CFG_ARCHIVE_ROOT_KEY) or '').strip()
    if not raw:
        return ''
    p = raw if os.path.isabs(raw) else os.path.join(BASE_DIR, raw)
    return os.path.abspath(os.path.expanduser(p))


def get_archive_settings():
    from server.core import load_config
    cfg = load_config()
    root = resolve_archive_root()
    return {
        'archive_root': str(cfg.get(_CFG_ARCHIVE_ROOT_KEY) or '').strip(),
        'archive_root_resolved': root,
        'auto_sync': bool(cfg.get(_CFG_ARCHIVE_AUTO_KEY, False)),
        'include': str(cfg.get(_CFG_ARCHIVE_INCLUDE_KEY) or 'both').strip() or 'both',
    }


def save_archive_settings(archive_root=None, auto_sync=None, include=None):
    from server.core import load_config, save_config
    cfg = load_config()
    if archive_root is not None:
        cfg[_CFG_ARCHIVE_ROOT_KEY] = str(archive_root or '').strip()
        roots = list(cfg.get('manual_qc_export_roots') or [])
        ar = str(archive_root or '').strip()
        if ar and ar not in roots:
            roots.append(ar)
            cfg['manual_qc_export_roots'] = roots
    if auto_sync is not None:
        cfg[_CFG_ARCHIVE_AUTO_KEY] = bool(auto_sync)
    if include is not None:
        inc = str(include or 'both').strip() or 'both'
        if inc not in ('both', 'platform', 'customer'):
            raise ValueError('include 须为 both / platform / customer')
        cfg[_CFG_ARCHIVE_INCLUDE_KEY] = inc
    save_config(cfg)
    return get_archive_settings()


def _write_coco_json(path, coco):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, indent=2)


def _platform_records_for_coco(rows):
    """仅含已导出平台图路径的记录。"""
    out = []
    for r in rows:
        rel = r.get('_export_platform_rel') or r.get('exported_platform')
        if not rel or not r.get('matched_img_path'):
            continue
        out.append(r)
    return out


def _write_export_coco_layers(out_dir, rows):
    """仅在 SN 目录（与图片同级）写入 _annotations.coco.json。"""
    platform_rows = _platform_records_for_coco(rows)
    if not platform_rows:
        return []

    by_sn_dir = {}
    for r in platform_rows:
        rel = (r.get('_export_platform_rel') or r.get('exported_platform') or '').replace('\\', '/')
        parts = [p for p in rel.split('/') if p]
        if len(parts) < 2:
            continue
        sn_key = tuple(parts[:-1])
        by_sn_dir.setdefault(sn_key, []).append(r)

    coco_paths = []
    for sn_key, items in by_sn_dir.items():
        coco = build_coco_from_manual_qc_records(
            items,
            file_name_fn=lambda r, _i: os.path.basename(
                (r.get('_export_platform_rel') or r.get('exported_platform') or '').replace('\\', '/'),
            ),
        )
        if coco.get('images'):
            p = os.path.join(out_dir, *sn_key, '_annotations.coco.json')
            _write_coco_json(p, coco)
            coco_paths.append(p)

    return coco_paths


def materialize_records_to_dir(rows, out_dir, include='both'):
    """将记录写入 <out_dir>/<年>/<月>/<日>/<成像类别>/<SN>/ 并在 SN 目录写 COCO。"""
    from studio.forge import forge_paths
    out_dir = os.path.abspath(out_dir)
    if not forge_paths.safe_export_dir(out_dir):
        raise ValueError('目录不在允许范围内（exports/ 或已配置的 manual_qc_export_roots / 归档根目录）')
    os.makedirs(out_dir, exist_ok=True)

    copied, missing = 0, 0
    manifest = []
    enriched = []
    for r in rows:
        date_prefix = _archive_date_prefix(r.get('archived_at'))
        cat_name = _safe_name(r.get('qc_category'))
        sn = _safe_name(r.get('product_no'), fallback='SN')
        sn_dir = os.path.join(out_dir, date_prefix, cat_name, sn)
        rid = r.get('id')
        record = {
            'id': rid, 'product_no': r.get('product_no'),
            'qc_category': r.get('qc_category'), 'defect_type': r.get('defect_type'),
            'product_type': r.get('product_type'), 'match_status': r.get('match_status'),
            'archived_at': r.get('archived_at'), 'note': r.get('note'),
            'exported_platform': '', 'exported_customer': '',
        }
        row_copy = dict(r)
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
            dst_name = f"{rid}__{kind}{ext}"
            os.makedirs(sn_dir, exist_ok=True)
            try:
                shutil.copy2(src, os.path.join(sn_dir, dst_name))
                copied += 1
                rel = os.path.join(date_prefix, cat_name, sn, dst_name).replace('\\', '/')
                record[f'exported_{kind}'] = rel
                if kind == 'platform':
                    row_copy['_export_platform_rel'] = rel
                    row_copy['exported_platform'] = rel
            except Exception:
                missing += 1
        manifest.append(record)
        enriched.append(row_copy)

    manifest_path = os.path.join(out_dir, 'manifest.csv')
    if manifest:
        with open(manifest_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(manifest[0].keys()))
            writer.writeheader()
            writer.writerows(manifest)

    coco_paths = _write_export_coco_layers(out_dir, enriched)
    return {
        'out_dir': out_dir,
        'records': len(rows),
        'copied': copied,
        'missing': missing,
        'manifest': manifest_path if manifest else None,
        'coco_paths': coco_paths,
        'coco_count': len(coco_paths),
    }


def sync_record_to_archive_root(rec=None, qc_id=None, force=False):
    """单条已定案记录同步到配置的归档根目录。"""
    settings = get_archive_settings()
    root = settings.get('archive_root_resolved') or ''
    if not root:
        return None
    if rec is None and qc_id is not None:
        rec = forge_db.get_manual_qc(qc_id)
    if not rec or rec.get('workflow_status') != WORKFLOW_ARCHIVED:
        return None
    include = settings.get('include') or 'both'
    if not force and not settings.get('auto_sync'):
        return None
    return materialize_records_to_dir([rec], root, include=include)


def sync_all_to_archive_root(start=None, end=None, categories=None, defect_types=None,
                            batch_id=None, limit=None):
    """将全部已定案记录同步到归档根目录。"""
    settings = get_archive_settings()
    root = settings.get('archive_root_resolved') or ''
    if not root:
        raise ValueError('请先在设置中配置人工质检归档根目录')
    rows = forge_db.list_manual_qc(
        start=start, end=end, categories=categories, defect_types=defect_types,
        batch_id=batch_id, limit=limit or 1000000, workflow_status=WORKFLOW_ARCHIVED,
    )
    return materialize_records_to_dir(rows, root, include=settings.get('include') or 'both')


def export_records(start=None, end=None, categories=None, defect_types=None,
                   out_dir=None, include='both', limit=None, as_zip=False):
    """按时段 + 类别导出图片到目录。

    include: 'platform' / 'customer' / 'both'。
    目录结构：<out_dir>/<年>/<月>/<日>/<成像类别>/<SN>/<id>__platform|customer.<ext>；
    SN 目录同级写入 _annotations.coco.json（含平台检测框）。
    并写 manifest.csv。as_zip=True 时打包下载。
    """
    rows = forge_db.list_manual_qc(
        start=start, end=end, categories=categories, defect_types=defect_types,
        limit=limit or 1000000, workflow_status=WORKFLOW_ARCHIVED,
    )
    if not out_dir:
        from studio.timezone_util import stamp_compact
        stamp = stamp_compact()
        out_dir = os.path.join(BASE_DIR, 'exports', 'manual_qc_export', stamp)
    result = materialize_records_to_dir(rows, out_dir, include=include or 'both')
    if as_zip:
        zip_base = result['out_dir'].rstrip('/\\')
        zip_path = shutil.make_archive(zip_base, 'zip', root_dir=result['out_dir'])
        result['zip_path'] = zip_path
    return result


def generate_training_handoff(start=None, end=None, categories=None, defect_types=None,
                              product_no=None, batch_id=None,
                              training_status='pending', note=None):
    """人工质检 → 标准训练交接包（COCO + images + manifest + provenance）。"""
    from studio.forge import forge_paths

    rows = forge_db.list_manual_qc(
        batch_id=batch_id, start=start, end=end, categories=categories,
        defect_types=defect_types, product_no=product_no,
        training_status=training_status, workflow_status=WORKFLOW_ARCHIVED, limit=100000,
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
    result['handoff_dir'] = out_dir
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
