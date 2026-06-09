"""按 SN 查询平台缺陷明细（查询与质检共用）。"""
from __future__ import annotations

from packages.platform.db import get_platform_db
from packages.platform.img_path import resolve_detail_img_path

DETAIL_SELECT = """
    SELECT d.id, d.product_no, d.origin_object_key, d.local_pic_url, d.ext, d.c_time,
           d.check_status, d.detection_result_status,
           r.product_type AS product_type
    FROM product_detection_detail_result d
    LEFT JOIN (
        SELECT product_no, MAX(product_type) AS product_type
        FROM product_detection_result GROUP BY product_no
    ) r ON d.product_no = r.product_no
"""


def _attach_img_paths(rows: list[dict]) -> list[dict]:
    for row in rows:
        row['img_path'] = resolve_detail_img_path(row)
    return rows


def find_records_by_sn(sn: str, *, limit: int = 50) -> list[dict]:
    sn = str(sn or '').strip()
    if not sn:
        return []
    client = get_platform_db()
    sql = DETAIL_SELECT + " WHERE d.product_no = %s ORDER BY d.id DESC LIMIT %s"
    try:
        rows = client.fetchall(sql, (sn, int(limit)))
    except Exception:
        rows = []
    return _attach_img_paths(rows)


def fetch_detail_record(detail_id: int) -> dict:
    client = get_platform_db()
    sql = DETAIL_SELECT + " WHERE d.id = %s LIMIT 1"
    try:
        row = client.fetchone(sql, (int(detail_id),))
    except Exception:
        row = None
    if row:
        row['img_path'] = resolve_detail_img_path(row)
    return row or {}
