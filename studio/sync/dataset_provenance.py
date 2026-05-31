"""同步数据集样本与 vision_backend 平台库联合溯源（SN / 款型 / 时间等）。"""
from __future__ import annotations

import logging
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from studio.query.row_fields import sn_from_path

logger = logging.getLogger('detforge.provenance')

FUZZY_MIN_RATIO = 0.72
FUZZY_MIN_STEM_LEN = 5
FUZZY_LIKE_MIN_LEN = 6

_DETAIL_LOOKUP = """
    SELECT d.id, d.product_no, d.product_id, d.origin_object_key, d.c_time,
           d.position, d.check_status,
           r.product_type AS product_type
    FROM product_detection_detail_result d
    LEFT JOIN (
        SELECT product_no, MAX(product_type) AS product_type
        FROM product_detection_result GROUP BY product_no
    ) r ON d.product_no = r.product_no
"""

_CHUNK = 200


def norm_object_key(key: Any) -> str:
    return _norm_key(key)


def _norm_key(key: Any) -> str:
    return str(key or '').replace('\\', '/').lstrip('/')


def _basename(key: Any) -> str:
    return Path(_norm_key(key)).name if key else ''


def _filename_fuzzy_score(a: str, b: str) -> float:
    """文件名模糊相似度 0~1（basename / stem，忽略大小写与前缀段）。"""
    qa = _fuzzy_compare_key(a)
    qb = _fuzzy_compare_key(b)
    if not qa or not qb:
        return 0.0
    if qa == qb:
        return 1.0
    if qa in qb or qb in qa:
        shorter, longer = (qa, qb) if len(qa) <= len(qb) else (qb, qa)
        return 0.88 + 0.12 * (len(shorter) / max(len(longer), 1))
    return SequenceMatcher(None, qa, qb).ratio()


def _fuzzy_compare_key(name: str) -> str:
    base = _basename(name).lower()
    if not base:
        return ''
    stem = Path(base).stem
    if '_' in stem:
        tail = stem.split('_', 1)[1]
        if len(tail) >= FUZZY_MIN_STEM_LEN:
            stem = tail
    alnum = re.sub(r'[^a-z0-9]', '', stem)
    if len(alnum) >= FUZZY_MIN_STEM_LEN:
        return alnum
    return stem


def _fuzzy_like_cores(name: str) -> List[str]:
    """提取可用于 SQL LIKE 的核心片段。"""
    cores = []
    seen = set()
    for candidate in _filename_variants(name):
        for token in (candidate, Path(candidate).stem, _fuzzy_compare_key(candidate)):
            token = str(token or '').strip().lower()
            if len(token) >= FUZZY_LIKE_MIN_LEN and token not in seen:
                seen.add(token)
                cores.append(token)
    return cores


def _best_row_for_filename(
    query_names: Iterable[str],
    rows: Iterable[dict],
    min_ratio: float = FUZZY_MIN_RATIO,
) -> Optional[Tuple[dict, float]]:
    best_row = None
    best_score = min_ratio
    queries = [q for q in query_names if q]
    for row in rows:
        target = row.get('origin_object_key') or ''
        for q in queries:
            score = _filename_fuzzy_score(q, target)
            if score > best_score:
                best_score = score
                best_row = row
    if best_row is None:
        return None
    return best_row, best_score


def _pick_fuzzy_from_map(
    fname_map: Dict[str, dict],
    file_name: str,
    object_key: str = '',
) -> Optional[Tuple[dict, float]]:
    queries = []
    for candidate in (file_name, object_key):
        for variant in _filename_variants(candidate):
            if variant:
                queries.append(variant)
    if not queries:
        return None
    return _best_row_for_filename(queries, fname_map.values())


def _pick_from_fuzzy_map(
    fuzzy_map: Dict[str, dict],
    file_name: str,
    object_key: str = '',
) -> Optional[dict]:
    for candidate in (file_name, object_key):
        for variant in _filename_variants(candidate):
            row = fuzzy_map.get(variant)
            if row:
                return row
    return None


def _filename_variants(name: str) -> List[str]:
    """收集可用于匹配的文件名变体（完整 basename + 去前缀后缀）。"""
    base = _basename(name)
    if not base:
        return []
    variants = {base}
    # Magic-Fox 导出常见：去掉第一个 _ 段前缀
    if '_' in base:
        parts = base.split('_', 1)
        if len(parts) == 2 and parts[1]:
            variants.add(parts[1])
    return [v for v in variants if v]


def _row_to_provenance(row: Optional[dict], status: str) -> dict:
    if not row:
        return {'trace_status': status or 'unmatched'}
    return {
        'source_detail_id': row.get('id'),
        'product_no': str(row.get('product_no') or '').strip() or None,
        'product_id': str(row.get('product_id') or '').strip() or None,
        'product_type': str(row.get('product_type') or '').strip() or None,
        'position': str(row.get('position') or '').strip() or None,
        'platform_c_time': row.get('c_time'),
        'matched_object_key': _norm_key(row.get('origin_object_key')) or None,
        'trace_status': status,
    }


def _lookup_by_object_keys(client, keys: Iterable[str]) -> Dict[str, dict]:
    uniq = []
    seen = set()
    for raw in keys:
        nk = _norm_key(raw)
        if not nk or nk in seen:
            continue
        seen.add(nk)
        uniq.append(nk)
    if not uniq:
        return {}

    out: Dict[str, dict] = {}
    for i in range(0, len(uniq), _CHUNK):
        chunk = uniq[i:i + _CHUNK]
        placeholders = ','.join(['%s'] * len(chunk))
        sql = _DETAIL_LOOKUP + f" WHERE d.origin_object_key IN ({placeholders})"
        try:
            rows = client.fetchall(sql, tuple(chunk))
        except Exception as e:  # noqa: BLE001
            logger.warning('object_key 溯源查询失败: %s', e)
            rows = []
        for row in rows or []:
            nk = _norm_key(row.get('origin_object_key'))
            if nk and nk not in out:
                out[nk] = row
    return out


def _basename_sql_expr() -> str:
    return "SUBSTRING_INDEX(REPLACE(d.origin_object_key, '\\\\', '/'), '/', -1)"


def _lookup_by_filenames(client, filenames: Iterable[str]) -> Dict[str, dict]:
    """按 origin_object_key 的 basename 批量匹配（文件名溯源主路径）。"""
    uniq = []
    seen = set()
    for raw in filenames:
        for variant in _filename_variants(raw):
            if variant and variant not in seen:
                seen.add(variant)
                uniq.append(variant)
    if not uniq:
        return {}

    expr = _basename_sql_expr()
    out: Dict[str, dict] = {}
    for i in range(0, len(uniq), _CHUNK):
        chunk = uniq[i:i + _CHUNK]
        placeholders = ','.join(['%s'] * len(chunk))
        sql = (
            _DETAIL_LOOKUP
            + f" WHERE {expr} IN ({placeholders}) ORDER BY d.id DESC"
        )
        try:
            rows = client.fetchall(sql, tuple(chunk))
        except Exception as e:  # noqa: BLE001
            logger.warning('文件名溯源查询失败: %s', e)
            rows = []
        for row in rows or []:
            fname = _basename(row.get('origin_object_key'))
            if fname and fname not in out:
                out[fname] = row
            # 去前缀变体也写入映射
            for variant in _filename_variants(fname):
                if variant not in out:
                    out[variant] = row
    return out


def _lookup_by_filename_suffix(client, filenames: Iterable[str]) -> Dict[str, dict]:
    """basename 未命中时，用 origin_object_key 后缀 LIKE '%/filename' 匹配。"""
    uniq = []
    seen = set()
    for raw in filenames:
        base = _basename(raw)
        if base and base not in seen:
            seen.add(base)
            uniq.append(base)
    if not uniq:
        return {}

    out: Dict[str, dict] = {}
    for i in range(0, len(uniq), 50):
        chunk = uniq[i:i + 50]
        conds = ' OR '.join(['d.origin_object_key LIKE %s'] * len(chunk))
        params = [f'%/{fn}' for fn in chunk]
        sql = _DETAIL_LOOKUP + f" WHERE ({conds}) ORDER BY d.id DESC"
        try:
            rows = client.fetchall(sql, tuple(params))
        except Exception as e:  # noqa: BLE001
            logger.warning('文件名后缀溯源查询失败: %s', e)
            rows = []
        for row in rows or []:
            ok = _norm_key(row.get('origin_object_key'))
            fname = _basename(ok)
            for fn in chunk:
                if ok.endswith('/' + fn) or ok == fn or fname == fn:
                    if fn not in out:
                        out[fn] = row
    return out


def _lookup_by_filename_fuzzy(client, filenames: Iterable[str]) -> Dict[str, dict]:
    """精确匹配失败后，用 SQL LIKE + 相似度评分做文件名模糊溯源。"""
    fn_to_cores: Dict[str, List[str]] = {}
    all_cores: List[str] = []
    core_seen = set()
    for raw in filenames:
        fn = _basename(raw)
        if not fn:
            continue
        cores = _fuzzy_like_cores(fn)
        if not cores:
            continue
        fn_to_cores[fn] = cores
        for c in cores:
            if c not in core_seen:
                core_seen.add(c)
                all_cores.append(c)
    if not fn_to_cores:
        return {}

    expr = _basename_sql_expr()
    candidate_rows: List[dict] = []
    row_seen = set()
    for i in range(0, len(all_cores), 40):
        chunk = all_cores[i:i + 40]
        conds = ' OR '.join([f'LOWER({expr}) LIKE %s'] * len(chunk))
        params = [f'%{c}%' for c in chunk]
        sql = _DETAIL_LOOKUP + f' WHERE ({conds}) ORDER BY d.id DESC LIMIT 800'
        try:
            rows = client.fetchall(sql, tuple(params))
        except Exception as e:  # noqa: BLE001
            logger.warning('文件名模糊溯源查询失败: %s', e)
            rows = []
        for row in rows or []:
            rid = row.get('id')
            if rid not in row_seen:
                row_seen.add(rid)
                candidate_rows.append(row)

    out: Dict[str, dict] = {}
    for fn, cores in fn_to_cores.items():
        queries = [fn] + cores
        picked = _best_row_for_filename(queries, candidate_rows)
        if not picked:
            continue
        row, score = picked
        out[fn] = row
        for variant in _filename_variants(fn):
            if variant not in out:
                out[variant] = row
        logger.debug('模糊溯源命中 %s score=%.3f -> %s', fn, score, row.get('origin_object_key'))
    return out


def _lookup_by_sns(client, sns: Iterable[str]) -> Dict[str, List[dict]]:
    uniq = []
    seen = set()
    for sn in sns:
        s = str(sn or '').strip()
        if not s or s in seen:
            continue
        seen.add(s)
        uniq.append(s)
    if not uniq:
        return {}

    out: Dict[str, List[dict]] = {s: [] for s in uniq}
    for i in range(0, len(uniq), _CHUNK):
        chunk = uniq[i:i + _CHUNK]
        placeholders = ','.join(['%s'] * len(chunk))
        sql = _DETAIL_LOOKUP + f" WHERE d.product_no IN ({placeholders}) ORDER BY d.id DESC"
        try:
            rows = client.fetchall(sql, tuple(chunk))
        except Exception as e:  # noqa: BLE001
            logger.warning('SN 溯源查询失败: %s', e)
            rows = []
        for row in rows or []:
            sn = str(row.get('product_no') or '').strip()
            if sn in out:
                out[sn].append(row)
    return out


def _pick_from_fname_map(fname_map: Dict[str, dict], file_name: str, object_key: str = '') -> Optional[dict]:
    for candidate in (file_name, object_key):
        for variant in _filename_variants(candidate):
            row = fname_map.get(variant)
            if row:
                return row
    return None


def resolve_item_provenance(
    object_key: str,
    file_name: str = '',
    key_map: Optional[Dict[str, dict]] = None,
    fname_map: Optional[Dict[str, dict]] = None,
    fuzzy_map: Optional[Dict[str, dict]] = None,
    sn_map: Optional[Dict[str, List[dict]]] = None,
) -> dict:
    """单条样本溯源：精确 → 文件名 → 模糊文件名 → SN+文件名 → SN → 路径 SN。"""
    key_map = key_map or {}
    fname_map = fname_map or {}
    fuzzy_map = fuzzy_map or {}
    sn_map = sn_map or {}

    nk = _norm_key(object_key)
    if nk and nk in key_map:
        return _row_to_provenance(key_map[nk], 'matched')

    if nk:
        fname = _basename(nk)
        for k, row in key_map.items():
            if k == nk or k.endswith('/' + nk) or nk.endswith('/' + k):
                return _row_to_provenance(row, 'matched')
            if fname and _basename(k) == fname:
                return _row_to_provenance(row, 'filename')

    row = _pick_from_fname_map(fname_map, file_name, object_key)
    if row:
        return _row_to_provenance(row, 'filename')

    fuzzy_pick = _pick_fuzzy_from_map(fname_map, file_name, object_key)
    if fuzzy_pick:
        row, _score = fuzzy_pick
        return _row_to_provenance(row, 'fuzzy')

    row = _pick_from_fuzzy_map(fuzzy_map, file_name, object_key)
    if row:
        return _row_to_provenance(row, 'fuzzy')

    sn = sn_from_path(object_key) or sn_from_path(file_name)
    fname = _basename(file_name or object_key)
    if sn and sn in sn_map:
        candidates = sn_map[sn]
        if fname:
            for cand in candidates:
                if _basename(cand.get('origin_object_key')) == fname:
                    return _row_to_provenance(cand, 'sn_only')
            for cand in candidates:
                ok = _norm_key(cand.get('origin_object_key'))
                if ok.endswith('/' + fname) or fname in ok:
                    return _row_to_provenance(cand, 'sn_only')
            fuzzy_sn = _best_row_for_filename([fname, object_key], candidates)
            if fuzzy_sn:
                row, _score = fuzzy_sn
                return _row_to_provenance(row, 'fuzzy')
        if len(candidates) == 1:
            return _row_to_provenance(candidates[0], 'sn_only')
        prov = _row_to_provenance(candidates[0], 'sn_only')
        prov['product_no'] = sn
        return prov

    if sn:
        return {'product_no': sn, 'trace_status': 'path_only'}

    return {'trace_status': 'unmatched'}


def batch_lookup_provenance(items: List[dict]) -> List[dict]:
    """批量溯源。items: [{object_key, file_name?}, ...]，返回与输入等长的 provenance 列表。"""
    from server.core import get_db_client

    if not items:
        return []

    client = get_db_client()
    keys = [_norm_key(it.get('object_key')) for it in items if _norm_key(it.get('object_key'))]
    filenames: List[str] = []
    for it in items:
        fn = _basename(it.get('file_name')) or _basename(it.get('object_key'))
        if fn:
            filenames.append(fn)

    key_map = _lookup_by_object_keys(client, keys)
    fname_map = _lookup_by_filenames(client, filenames)

    missing = [fn for fn in filenames if not _pick_from_fname_map(fname_map, fn)]
    if missing:
        suffix_map = _lookup_by_filename_suffix(client, missing)
        fname_map.update(suffix_map)

    still_missing = [fn for fn in filenames if not _pick_from_fname_map(fname_map, fn)]
    fuzzy_map = _lookup_by_filename_fuzzy(client, still_missing) if still_missing else {}

    unmatched_sns = []
    for it in items:
        nk = _norm_key(it.get('object_key'))
        fn = _basename(it.get('file_name')) or _basename(it.get('object_key'))
        already = (
            (nk and nk in key_map)
            or _pick_from_fname_map(fname_map, fn, nk)
            or _pick_from_fuzzy_map(fuzzy_map, fn, nk)
        )
        if already:
            continue
        sn = sn_from_path(it.get('object_key')) or sn_from_path(it.get('file_name'))
        if sn:
            unmatched_sns.append(sn)

    sn_map = _lookup_by_sns(client, unmatched_sns) if unmatched_sns else {}

    return [
        resolve_item_provenance(
            str(it.get('object_key') or ''),
            str(it.get('file_name') or ''),
            key_map=key_map,
            fname_map=fname_map,
            fuzzy_map=fuzzy_map,
            sn_map=sn_map,
        )
        for it in items
    ]


def retrace_dataset_items(dataset_id: int, log_fn=None) -> dict:
    """对已写入 dataset_item 的全量样本重新执行平台库溯源。"""
    from studio.forge import forge_db

    _log = log_fn or (lambda _m: None)
    rows = forge_db.list_dataset_items(int(dataset_id), limit=100000, offset=0)
    if not rows:
        return {'dataset_id': int(dataset_id), 'total': 0, 'updated': 0}

    lookup_items = [
        {'object_key': r.get('object_key'), 'file_name': r.get('file_name')}
        for r in rows
    ]
    _log(f'溯源 {len(lookup_items)} 条样本（精确 + 模糊文件名 + SN）…')
    prov_list = batch_lookup_provenance(lookup_items)

    updated = 0
    for row, prov in zip(rows, prov_list):
        forge_db.update_dataset_item_provenance(int(row['id']), prov)
        updated += 1

    summary = forge_db.dataset_item_trace_summary(int(dataset_id))
    _log(
        f'溯源完成：matched={summary.get("matched", 0)} '
        f'filename={summary.get("filename", 0)} '
        f'fuzzy={summary.get("fuzzy", 0)} '
        f'sn_only={summary.get("sn_only", 0)} '
        f'path_only={summary.get("path_only", 0)} '
        f'unmatched={summary.get("unmatched", 0)}'
    )
    return {
        'dataset_id': int(dataset_id),
        'total': len(rows),
        'updated': updated,
        'trace_summary': summary,
    }
