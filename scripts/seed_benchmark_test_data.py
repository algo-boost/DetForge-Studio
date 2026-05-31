#!/usr/bin/env python3
"""将本地 benchmark 图片 + COCO 标注写入 vision_backend，字段对齐产线表结构。"""
import argparse
import json
import re
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

import pymysql

BENCHMARK_ROOT = Path("/Users/rookie/Desktop/benchmark构建")
DEFAULT_SOURCE = BENCHMARK_ROOT / "yfmb_benchmark-pos_0526"
PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"

PRODUCT_PREFIX = "DLTEST"
DEFAULT_LIMIT = 0
IMAGE_EXTS = {".jpg", ".jpeg"}
FILENAME_RE = re.compile(r"_(p_\d+)_([0-9a-f]{32})_", re.I)

# 产线样例行常用占位（未知字段按原库风格编造）
DEFAULT_PIPELINE_ID = "4a19605f-518c-4ac3-8042-f202dcd9b8e3"
DEFAULT_NODE_ID = "0c737a53-f684-4927-9c85-934324b80e24"
DEFAULT_PRODUCT_TYPE = "F2A_BACKEND_RIGHT"
DEFAULT_NODE_FULL_NAME = "36_目标检测"
DEFAULT_CONFIDENCE = 0.88


def load_config():
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)


def name_to_defect_type(name: str, id2name: dict) -> str:
    name = (name or "").strip()
    for k, v in id2name.items():
        if v == name:
            return str(k)
    return "14"


def bbox_to_prediction(name: str, bbox, score=None):
    x, y, w, h = [float(v) for v in bbox[:4]]
    conf = DEFAULT_CONFIDENCE if score is None else float(score)
    return {
        "name": name,
        "confidence": conf,
        "type": "bounding_box",
        "points": [{"x": x, "y": y, "w": w, "h": h, "confidence": None}],
    }


def build_ext(predictions: list) -> str:
    payload = {"original_predictions": predictions}
    if predictions:
        payload["node_full_name"] = DEFAULT_NODE_FULL_NAME
    return json.dumps(payload, ensure_ascii=False)


def build_infer_raw(predictions: list) -> str:
    return json.dumps(
        {"predictions": list(predictions), "heat_map_object_key": None},
        ensure_ascii=False,
    )


def parse_filename_meta(file_name: str, fallback_idx: int):
    m = FILENAME_RE.search(file_name)
    product_no = f"{PRODUCT_PREFIX}-{fallback_idx:04d}"
    if m:
        position = m.group(1).lower()
        product_id = m.group(2)
        return position, product_id, product_no
    return f"p_{fallback_idx:03d}", product_no, product_no


def load_coco_bundle(source_dir: Path):
    coco_path = source_dir / "_annotations.coco.json"
    if not coco_path.is_file():
        return None
    with open(coco_path, encoding="utf-8") as f:
        data = json.load(f)
    cats = {int(c["id"]): c["name"] for c in data.get("categories", [])}
    anns_by_img: dict[int, list] = {}
    for ann in data.get("annotations", []):
        anns_by_img.setdefault(int(ann["image_id"]), []).append(ann)
    images = sorted(data.get("images", []), key=lambda x: str(x.get("file_name", "")))
    return {"path": coco_path, "data": data, "cats": cats, "anns_by_img": anns_by_img, "images": images}


def predictions_from_coco(image_id: int, cats: dict, anns_by_img: dict) -> list:
    out = []
    for ann in anns_by_img.get(int(image_id), []):
        name = cats.get(int(ann.get("category_id", -1)), "未知")
        score = ann.get("score")
        if score is None:
            score = ann.get("confidence")
        out.append(bbox_to_prediction(name, ann.get("bbox") or [0, 0, 1, 1], score=score))
    return out


def iter_disk_images(source_dir: Path, limit: int):
    found = []
    for path in sorted(source_dir.rglob("*")):
        if path.suffix.lower() in IMAGE_EXTS and is_product_image(path):
            found.append(path)
            if limit and len(found) >= limit:
                break
    return found


def is_product_image(path: Path) -> bool:
    name = path.name.lower()
    return name.startswith("_p_") or name.startswith("p_")


def resolve_local_path(source_dir: Path, file_name: str) -> Path:
    direct = source_dir / file_name
    if direct.is_file():
        return direct.resolve()
    for p in source_dir.rglob(file_name):
        if p.is_file():
            return p.resolve()
    return direct.resolve()


def seed(source_dir=None, limit=DEFAULT_LIMIT, on_date=None, dry_run=False):
    source_dir = Path(source_dir or DEFAULT_SOURCE).resolve()
    on_date = on_date or date.today()
    base_time = datetime.combine(on_date, datetime.min.time()).replace(hour=10, minute=0, second=0)

    cfg = load_config()
    id2name = cfg.get("id2name") or {}

    coco = load_coco_bundle(source_dir)
    entries = []

    if coco:
        for i, img in enumerate(coco["images"]):
            if limit and i >= limit:
                break
            file_name = str(img.get("file_name") or "").strip()
            if not file_name:
                continue
            local_path = resolve_local_path(source_dir, file_name)
            if not local_path.is_file():
                print(f"  skip missing file: {file_name}")
                continue
            preds = predictions_from_coco(img["id"], coco["cats"], coco["anns_by_img"])
            position, product_id, product_no = parse_filename_meta(file_name, i + 1)
            if img.get("product_id"):
                product_id = str(img["product_id"])
            primary = preds[0]["name"] if preds else "脏污"
            entries.append(
                _build_row(
                    idx=i,
                    file_name=file_name,
                    local_path=local_path,
                    source_dir=source_dir,
                    preds=preds,
                    primary_name=primary,
                    id2name=id2name,
                    position=position,
                    product_id=product_id,
                    product_no=product_no,
                    base_time=base_time,
                )
            )
    else:
        disk_images = iter_disk_images(source_dir, limit)
        for i, local_path in enumerate(disk_images):
            preds = []  # 无 COCO 时不造框
            position, product_id, product_no = parse_filename_meta(local_path.name, i + 1)
            entries.append(
                _build_row(
                    idx=i,
                    file_name=local_path.name,
                    local_path=local_path,
                    source_dir=source_dir,
                    preds=preds,
                    primary_name="脏污",
                    id2name=id2name,
                    position=position,
                    product_id=product_id,
                    product_no=product_no,
                    base_time=base_time,
                )
            )

    if not entries:
        raise SystemExit(f"在 {source_dir} 下未找到可导入图片")

    conn = pymysql.connect(
        host=cfg["db_host"],
        user=cfg["db_user"],
        password=cfg.get("db_password", ""),
        database=cfg["db_database"],
        charset="utf8mb4",
    )

    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM product_detection_detail_result WHERE product_no LIKE %s",
                (f"{PRODUCT_PREFIX}-%",),
            )
            deleted = cur.rowcount
            print(f"已清理旧测试数据: {deleted} 行")

            if dry_run:
                sample = entries[0]
                print(f"[dry-run] 将写入 {len(entries)} 行")
                print(f"  示例 SN: {sample[10]}")
                print(f"  示例 ext 框数: {len(json.loads(sample[17]).get('original_predictions', []))}")
                return len(entries)

            sql = """
                INSERT INTO product_detection_detail_result
                    (pipeline_id, product_id, position, defect_type, pic_url, local_pic_url,
                     infer_raw_result, check_status, c_time, m_time, product_no, product_type,
                     detection_result_status, manual_check_status, node_id, origin_object_key,
                     ng_result_uuid, ext, detection_version, is_latest_version)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """
            cur.executemany(sql, entries)
        conn.commit()

    ann_total = sum(
        len(json.loads(r[17]).get("original_predictions", [])) for r in entries
    )
    print(f"已导入 {len(entries)} 条测试记录 ({PRODUCT_PREFIX}-*)")
    print(f"  源目录: {source_dir}")
    print(f"  COCO 标注框合计: {ann_total} 个")
    print(f"  时间范围: {entries[0][8]} ~ {entries[-1][8]}（均为 {on_date}）")
    return len(entries)


def _build_row(
    *,
    idx,
    file_name,
    local_path,
    source_dir,
    preds,
    primary_name,
    id2name,
    position,
    product_id,
    product_no,
    base_time,
):
    c_time = base_time + timedelta(minutes=idx)
    subdir = source_dir.name
    rel_key = f"benchmark/{subdir}/{file_name}"
    abs_path = str(local_path)
    pic_url = f"machine_vision/benchmark/{subdir}/{file_name}"
    ext = build_ext(preds)
    infer = build_infer_raw(preds) if preds else None
    defect_type = name_to_defect_type(primary_name, id2name)

    return (
        DEFAULT_PIPELINE_ID,
        product_id,
        position,
        defect_type,
        pic_url,
        abs_path,
        infer,
        "1",
        c_time,
        c_time,
        product_no,
        DEFAULT_PRODUCT_TYPE,
        "ng",
        "ng",
        DEFAULT_NODE_ID,
        rel_key,
        str(uuid.uuid4()),
        ext,
        "0",
    )


def main():
    parser = argparse.ArgumentParser(description="导入 benchmark 图片与 COCO 标注到 vision_backend")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="benchmark 目录")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="最多导入张数，0=全部")
    parser.add_argument("--date", default="", help="检测日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    on_date = date.fromisoformat(args.date) if args.date else date.today()
    seed(source_dir=args.source, limit=args.limit, on_date=on_date, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
