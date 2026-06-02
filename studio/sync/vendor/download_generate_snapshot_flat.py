#!/usr/bin/env python3
"""
从「数据增强快照」拉取图片列表并下载到同一目录（不经 export_snapshot 整包）。

接口：GET {base_url}/generate_datasets/detail/{generate_id}
     返回 data.dataset_items，每项含 object_key / object_name。

下载：POST {base_url}/objects/download_files（body: object_key 列表）换临时 URL，再 GET 落盘。

文件名：默认与平台导出后执行 rename_coco_imgnames 一致——去掉 object_name 中第一个下划线及其前面的段
（例如 1775148302064_db5f3ab5-e.jpeg -> db5f3ab5-e.jpeg）。

目录：默认「全部在同一目录」扁平输出（COCO 与图片同级）。如需与平台 zip 一致分层，可加 --split-subdirs
按 split_type 写入 train/、valid/、test/ 子目录，COCO 中 file_name 为相对路径（如 train/foo.jpg）。

标注：使用与 magic-fox-coco-download 相同的 convert_to_coco / generate_stats，输出 _annotations.coco.json
与 stats.json。说明：generate_datasets/detail 返回的 annotations 不含 meta/shapes，脚本会再请求
GET /dataset_items/{dataset_item_id} 拉全量标注并与快照中的 object_key / object_name / id 合并，
与平台导出 zip 内 COCO 逻辑一致。

用法示例：
  HTTP_PROXY= HTTPS_PROXY= python download_generate_snapshot_flat.py \\
    --generate-id 6630 \\
    --output-dir ~/Desktop/延锋_dataset_snapshots/延锋门板-误检集_V64

  # 底库数据集（dataset_id，不经快照 ID / 不经 export_snapshot 整包）：
  HTTP_PROXY= HTTPS_PROXY= python download_generate_snapshot_flat.py \\
    --dataset-id 3151 \\
    --output-dir ~/Desktop/my_dataset_export
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import moli_dataset_export as m

DEFAULT_DOWNLOAD_FILES = "objects/download_files"


def _ensure_coco_export_path() -> Path:
    vendor_dir = Path(__file__).resolve().parent
    if (vendor_dir / 'coco_export.py').is_file():
        if str(vendor_dir) not in sys.path:
            sys.path.insert(0, str(vendor_dir))
        return vendor_dir
    raise ImportError(f'找不到 coco_export.py（期望位于 {vendor_dir}）')


_ensure_coco_export_path()
from coco_export import convert_to_coco, fetch_labels_map, generate_stats  # noqa: E402


def strip_export_filename(file_name: str) -> str:
    """
    与 moli_dataset_export.rename_coco_imgnames 一致：去掉第一个 `_` 前的段。
    平台导出 zip 内常见为「时间戳_原文件名」。
    """
    if not file_name:
        return file_name
    parts = file_name.split("_")
    if len(parts) < 2:
        return file_name
    new_name = "_".join(parts[1:])
    if not new_name or new_name == file_name:
        return file_name
    return new_name


def assign_dedup_name(stripped: str, counts: Counter[str]) -> str:
    """同一目录下 stripped 冲突时追加 __dupN（与旧版脚本一致）。"""
    idx = counts[stripped]
    counts[stripped] += 1
    if idx == 0:
        return stripped
    stem = Path(stripped).stem
    suf = Path(stripped).suffix
    return f"{stem}__dup{idx}{suf}"


def split_type_to_subdir(split_raw: Any) -> str:
    """
    与平台 zip 导出一致：图片落在 train / valid / test 子目录。
    将线上 split_type 规范为上述目录名（小写）。
    """
    if split_raw is None:
        return "train"
    if isinstance(split_raw, int):
        return {0: "train", 1: "valid", 2: "test"}.get(split_raw, "train")
    s = str(split_raw).strip().lower()
    if not s:
        return "train"
    if s in ("train", "training"):
        return "train"
    if s in ("valid", "validation", "val", "dev"):
        return "valid"
    if s in ("test", "testing"):
        return "test"
    if s in ("0", "1", "2"):
        return {"0": "train", "1": "valid", "2": "test"}.get(s, "train")
    raw = str(split_raw)
    if "测试" in raw:
        return "test"
    if "验证" in raw:
        return "valid"
    if "训练" in raw:
        return "train"
    return "train"


def fetch_dataset_items_all_pages(base_url: str, token: str, dataset_id: int) -> List[Dict[str, Any]]:
    """
    底库数据集：GET /dataset_items/page?dataset_id=…（分页），返回 data.dataset_items 全量行。
    用于不经 generate_datasets / export_snapshot 整包，直接按数据集 ID 导出。
    """
    base = base_url.rstrip("/")
    s = m._api_session()
    out: List[Dict[str, Any]] = []
    skip = 0
    limit = 100
    total: Optional[int] = None
    while True:
        r = s.get(
            f"{base}/dataset_items/page",
            params={"dataset_id": int(dataset_id), "skip": skip, "limit": limit},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Origin": "https://www.ai.magic-fox.com",
                "Referer": "https://www.ai.magic-fox.com/",
            },
            proxies=m._direct_proxies(),
            timeout=300,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("code") != 200 or not data.get("success"):
            raise RuntimeError(f"dataset_items/page 失败: {data.get('msg', data)}")
        payload = data.get("data") or {}
        if total is None:
            total = int(payload.get("total_count") or 0)
        chunk = payload.get("dataset_items") or []
        out.extend(chunk)
        skip += len(chunk)
        if not chunk or (total and skip >= total):
            break
    return out


def dataset_page_rows_to_detail_items(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将 dataset_items/page 行转为 hydrate 所需的「快照行」形态（id 与 dataset_item_id 均为底库项 id）。"""
    detail_items: List[Dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        iid = row.get("id")
        if iid is None:
            continue
        detail_items.append(
            {
                "id": int(iid),
                "dataset_item_id": int(iid),
                "object_name": row.get("object_name"),
                "object_key": row.get("object_key"),
                "split_type": row.get("split_type"),
                "c_time": row.get("c_time"),
                "m_time": row.get("m_time"),
            }
        )
    return detail_items


def fetch_dataset_meta(base_url: str, token: str, dataset_id: int) -> Dict[str, Any]:
    """GET /datasets/{id}，取 dataset_name、approach_id 等。"""
    url = f"{base_url.rstrip('/')}/datasets/{int(dataset_id)}"
    s = m._api_session()
    r = s.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://www.ai.magic-fox.com",
            "Referer": "https://www.ai.magic-fox.com/",
        },
        proxies=m._direct_proxies(),
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200 or not data.get("success"):
        raise RuntimeError(f"datasets/{dataset_id} 失败: {data.get('msg', data)}")
    row = data.get("data")
    if not isinstance(row, dict):
        raise RuntimeError(f"datasets/{dataset_id} 返回 data 非对象")
    return row


def fetch_generate_detail(base_url: str, token: str, generate_id: int) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}/generate_datasets/detail/{generate_id}"
    s = m._api_session()
    r = s.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://www.ai.magic-fox.com",
            "Referer": "https://www.ai.magic-fox.com/",
        },
        proxies=m._direct_proxies(),
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200 or not data.get("success"):
        raise RuntimeError(f"generate_datasets/detail 失败: {data.get('msg', data)}")
    payload = data.get("data") or {}
    items = payload.get("dataset_items") or []
    meta_count = payload.get("count")
    if meta_count is not None and len(items) != int(meta_count):
        print(
            f"⚠️ 提示: count={meta_count} 与 dataset_items 条数 {len(items)} 不一致，以列表为准",
            file=sys.stderr,
        )
    return payload


def fetch_dataset_item_row(base_url: str, token: str, dataset_item_id: int) -> Dict[str, Any]:
    """GET /dataset_items/{id}，含完整 annotations（meta、shapes）。"""
    url = f"{base_url.rstrip('/')}/dataset_items/{int(dataset_item_id)}"
    s = m._api_session()
    r = s.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Origin": "https://www.ai.magic-fox.com",
            "Referer": "https://www.ai.magic-fox.com/",
        },
        proxies=m._direct_proxies(),
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200 or not data.get("success"):
        raise RuntimeError(f"dataset_items/{dataset_item_id} 失败: {data.get('msg', data)}")
    row = data.get("data")
    if not isinstance(row, dict):
        raise RuntimeError(f"dataset_items/{dataset_item_id} 返回 data 非对象")
    return row


def merge_snapshot_row_for_coco(detail: Dict[str, Any], full: Dict[str, Any]) -> Dict[str, Any]:
    """
    以单条 dataset_items 全量为准，但保留快照行的 id / object_name / object_key（与下载文件一致）。
    """
    out = dict(full)
    out["id"] = detail["id"]
    out["object_name"] = detail["object_name"]
    out["object_key"] = detail["object_key"]
    out["dataset_item_id"] = detail.get("dataset_item_id")
    out["generate_id"] = detail.get("generate_id")
    out["split_type"] = detail.get("split_type", full.get("split_type"))
    out["c_time"] = detail.get("c_time", full.get("c_time"))
    out["m_time"] = detail.get("m_time", full.get("m_time"))
    out["annotations"] = full.get("annotations")
    out["labels"] = full.get("labels")
    out["annotation_status"] = full.get("annotation_status")
    return out


def hydrate_items_for_coco(
    detail_items: List[Dict[str, Any]],
    base_url: str,
    token: str,
    workers: int,
) -> List[Dict[str, Any]]:
    """对每条快照记录拉取 dataset_items 全量标注，供 convert_to_coco 使用。"""
    n = len(detail_items)
    print(f"拉取每条 dataset_items 全量标注（共 {n} 条，并发={workers}）…")

    def job(idx: int, detail: Dict[str, Any]) -> Tuple[int, Optional[Dict[str, Any]]]:
        di_id = detail.get("dataset_item_id")
        if di_id is None:
            raise RuntimeError(f"第 {idx} 条缺少 dataset_item_id: {detail.get('object_name')}")
        try:
            full = fetch_dataset_item_row(base_url, token, int(di_id))
        except RuntimeError as e:
            msg = str(e).lower()
            if "item not found" in msg or "not found" in msg:
                oname = detail.get("object_name") or ""
                print(
                    f"  跳过（dataset_items 不存在）: {idx+1}/{n} "
                    f"dataset_item_id={di_id} object_name={oname!r}"
                )
                return idx, None
            raise
        return idx, merge_snapshot_row_for_coco(detail, full)

    merged: List[Optional[Dict[str, Any]]] = [None] * n
    done = 0
    with ThreadPoolExecutor(max_workers=max(1, int(workers))) as ex:
        futures = {ex.submit(job, i, it): i for i, it in enumerate(detail_items)}
        for fut in as_completed(futures):
            idx, row = fut.result()
            if row is not None:
                merged[idx] = row
            done += 1
            if done % 300 == 0 or done == n:
                print(f"  已合并标注 {done}/{n}")
    kept = [m for m in merged if m is not None]
    skipped = n - len(kept)
    if skipped:
        print(f"   hydrate 结束: 可用 {len(kept)} 条，跳过 {skipped} 条（服务端无对应 dataset_item）")
    return kept


def fetch_download_urls(
    base_url: str,
    token: str,
    object_keys: Sequence[str],
) -> Dict[str, str]:
    path = DEFAULT_DOWNLOAD_FILES
    if not path.startswith("/"):
        path = "/" + path
    url = f"{base_url.rstrip('/')}{path}"
    s = m._api_session()
    r = s.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Origin": "https://www.ai.magic-fox.com",
            "Referer": "https://www.ai.magic-fox.com/",
        },
        json=list(object_keys),
        proxies=m._direct_proxies(),
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    if data.get("code") != 200 or not data.get("success"):
        raise RuntimeError(f"download_files 失败: {data.get('msg', data)}")
    return ((data.get("data") or {}).get("urls")) or {}


def download_batches(
    base_url: str,
    token: str,
    tasks: List[Tuple[str, Path]],
    batch_size: int,
    timeout_sec: int,
    retries: int,
    progress_fn=None,
) -> Tuple[int, int]:
    """tasks: (object_key, local_path)"""
    s = m._api_session()
    ok, fail = 0, 0
    total = len(tasks)
    for start in range(0, total, batch_size):
        batch = tasks[start : start + batch_size]
        keys = [k for k, _ in batch]
        print(f"换取下载 URL: {start + 1}-{start + len(batch)} / {total}")
        try:
            urls_map = fetch_download_urls(base_url, token, keys)
        except Exception as e:
            print(f"❌ 本批换取 URL 失败: {e}", file=sys.stderr)
            fail += len(batch)
            continue
        for object_key, local_path in batch:
            url = urls_map.get(object_key)
            if not url:
                print(f"⚠️ 无 URL，跳过: {object_key[:80]}...", file=sys.stderr)
                fail += 1
                continue
            done = False
            tmp = local_path.with_suffix(local_path.suffix + ".tmp")
            for attempt in range(retries + 1):
                try:
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    with s.get(url, stream=True, timeout=timeout_sec, proxies=m._direct_proxies()) as resp:
                        resp.raise_for_status()
                        with open(tmp, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                    os.replace(tmp, local_path)
                    done = True
                    break
                except Exception as e:
                    if attempt >= retries:
                        print(f"❌ 下载失败 {local_path.name}: {e}", file=sys.stderr)
                    try:
                        if tmp.exists():
                            tmp.unlink()
                    except Exception:
                        pass
            if done:
                ok += 1
            else:
                fail += 1
        print(f"进度: 成功={ok}, 失败={fail}, 已处理={ok + fail}/{total}")
        if progress_fn:
            try:
                progress_fn(ok + fail, total, ok, fail)
            except Exception:
                pass
    return ok, fail


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(
        description="从 generate_datasets/detail 下载快照图片（可选去前缀）并生成与平台导出一致的 COCO"
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--generate-id", type=int, default=None, help="快照/生成任务 ID（如 6630）")
    src.add_argument(
        "--dataset-id",
        type=int,
        default=None,
        help="底库数据集 ID（如 generate 详情中的 dataset_id）；走 dataset_items/page，不经快照 ID",
    )
    p.add_argument("--output-dir", type=Path, required=True, help="输出目录（扁平：图片 + COCO + stats）")
    p.add_argument("--batch-size", type=int, default=200, help="每批换取 URL 的 object_key 数量")
    p.add_argument("--timeout-sec", type=int, default=120, help="单文件下载超时")
    p.add_argument("--retries", type=int, default=2, help="单文件失败重试次数")
    p.add_argument("--skip-existing", action="store_true", help="已存在且非空则跳过下载")
    p.add_argument("--manifest-only", action="store_true", help="只写 manifest/COCO/stats，不下载图片")
    p.add_argument(
        "--no-strip-prefix",
        action="store_true",
        help="保留平台 object_name 作为本地文件名与 COCO file_name（默认会去掉第一个下划线前的段，与 rename_coco_imgnames 一致）",
    )
    p.add_argument("--annotations-name", default="_annotations.coco.json", help="COCO 文件名")
    p.add_argument("--stats-name", default="stats.json", help="统计 JSON 文件名")
    p.add_argument("--approach-id", type=int, default=None, help="覆盖自动从快照详情读取的 approach_id（用于 labels）")
    p.add_argument(
        "--hydrate-workers",
        type=int,
        default=8,
        help="拉取 dataset_items 全量标注时的并发数（默认 8）",
    )
    p.add_argument(
        "--split-subdirs",
        action="store_true",
        help="按划分建 train/valid/test 子目录（默认不分子目录，图片与 COCO 同层）",
    )
    args = p.parse_args(argv)

    strip_prefix = not bool(args.no_strip_prefix)
    use_split_subdirs = bool(args.split_subdirs)

    base, user, pw, _ = m.load_api_credentials()
    print("登录中…")
    token = m.login_and_get_token(base, user, pw)
    if not token:
        print("登录失败", file=sys.stderr)
        return 1

    detail_items: List[Dict[str, Any]]
    detail_for_approach: Optional[Dict[str, Any]] = None

    if args.dataset_id is not None:
        print(f"拉取底库数据集 dataset_id={args.dataset_id}（dataset_items/page）…")
        meta = fetch_dataset_meta(base, token, int(args.dataset_id))
        dname = (meta.get("dataset_name") or "").strip() or f"dataset_{args.dataset_id}"
        print(f"数据集名称: {dname}")
        page_rows = fetch_dataset_items_all_pages(base, token, int(args.dataset_id))
        detail_items = dataset_page_rows_to_detail_items(page_rows)
        if not detail_items:
            print("未获取到任何 dataset_items（底库分页为空）", file=sys.stderr)
            return 1
        print(f"共 {len(detail_items)} 条底库样本")
        detail_for_approach = meta
    else:
        assert args.generate_id is not None
        print(f"拉取快照详情 generate_id={args.generate_id} …")
        detail_for_approach = fetch_generate_detail(base, token, int(args.generate_id))
        detail_items = detail_for_approach.get("dataset_items") or []
        if not detail_items:
            print("未获取到任何 dataset_items", file=sys.stderr)
            return 1
        print(f"共 {len(detail_items)} 条快照记录")

    items = hydrate_items_for_coco(detail_items, base, token, args.hydrate_workers)

    approach_id: Optional[int] = args.approach_id
    if approach_id is None and detail_for_approach is not None:
        raw = detail_for_approach.get("approach_id")
        if raw is not None:
            try:
                approach_id = int(raw)
            except (TypeError, ValueError):
                approach_id = None

    label_definitions = None
    if approach_id is not None:
        try:
            label_definitions = fetch_labels_map(approach_id, token)
            print(f"已拉取 labels: approach_id={approach_id}, 数量={len(label_definitions)}")
        except Exception as e:
            print(f"⚠️ 拉取 labels 失败（将仅用标注内信息）: {e}")

    print("转换为 COCO …")
    coco_data, category_stats = convert_to_coco(items, label_definitions)

    by_id: Dict[Any, Dict[str, Any]] = {}
    for it in items:
        iid = it.get("id")
        if iid is not None:
            by_id[iid] = it

    name_counts: Dict[str, Counter[str]] = defaultdict(Counter)
    tasks: List[Tuple[str, Path]] = []
    manifest: List[Dict[str, Any]] = []

    out: Path = args.output_dir.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)

    coco_image_ids = {img["id"] for img in coco_data.get("images", [])}
    skipped_no_coco = len(items) - len(coco_image_ids)
    if skipped_no_coco:
        print(
            f"说明: {skipped_no_coco} 条记录在 convert_to_coco 中未进入 COCO（多为宽高为 0），将不下载对应图片。"
        )

    for image in coco_data["images"]:
        iid = image.get("id")
        orig_fn = (image.get("file_name") or "").strip()
        item = by_id.get(iid)
        if not item or not orig_fn:
            continue
        key = (item.get("object_key") or "").strip()
        if not key:
            continue

        subdir = split_type_to_subdir(item.get("split_type")) if use_split_subdirs else ""
        cnt = name_counts[subdir] if use_split_subdirs else name_counts[""]

        if strip_prefix:
            stripped = strip_export_filename(orig_fn)
            final_fn = assign_dedup_name(stripped, cnt)
        else:
            final_fn = assign_dedup_name(orig_fn, cnt)

        if use_split_subdirs:
            image["file_name"] = f"{subdir}/{final_fn}"
        else:
            image["file_name"] = final_fn

        manifest.append(
            {
                "object_name_online": orig_fn,
                "saved_as": final_fn,
                "split_subdir": subdir if use_split_subdirs else "",
                "coco_file_name": image["file_name"],
                "strip_prefix": strip_prefix,
                "object_key": key,
                "dataset_item_id": item.get("dataset_item_id"),
                "coco_image_id": iid,
            }
        )

        dest = (out / subdir / final_fn) if use_split_subdirs else (out / final_fn)
        if args.skip_existing and dest.exists() and dest.stat().st_size > 0:
            continue
        tasks.append((key, dest))

    ann_name = str(args.annotations_name).strip() or "_annotations.coco.json"
    if not ann_name.lower().endswith(".json"):
        ann_name = f"{ann_name}.json"
    stats_name = str(args.stats_name).strip() or "stats.json"
    if not stats_name.lower().endswith(".json"):
        stats_name = f"{stats_name}.json"

    ann_path = out / ann_name
    ann_path.write_text(json.dumps(coco_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 COCO: {ann_path}")

    stats = generate_stats(coco_data, category_stats)
    stats_path = out / stats_name
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入统计: {stats_path}")

    man_path = out / "manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入清单: {man_path}")

    if args.manifest_only:
        print("--manifest-only：跳过下载")
        return 0

    layout = "train|valid|test 子目录" if use_split_subdirs else "扁平（无划分子目录）"
    print(f"待下载 {len(tasks)} 个文件（与 COCO 中 images 一致）-> {out}  [{layout}]")
    ok, fail = download_batches(
        base,
        token,
        tasks,
        batch_size=args.batch_size,
        timeout_sec=args.timeout_sec,
        retries=args.retries,
    )
    print(f"完成: 成功={ok}, 失败={fail}, 目录={out}")
    return 0 if fail == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
