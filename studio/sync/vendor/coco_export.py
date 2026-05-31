import argparse
import json
import os
import time
import contextlib
import io
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple
from urllib.parse import parse_qs, urlparse

import requests
from requests.exceptions import JSONDecodeError as RequestsJSONDecodeError


DEFAULT_DOWNLOAD_FILES_URL = "https://www.ai.magic-fox.com/api/v1/objects/download_files"
DEFAULT_DATASET_ITEMS_PAGE_URL = "https://www.ai.magic-fox.com/api/v1/dataset_items/page"
DEFAULT_LABELS_URL = "https://www.ai.magic-fox.com/api/v1/labels/"


def normalize_access_token(access_token: str) -> str:
    return (access_token or "").replace("\n", "").replace("\r", "").replace(" ", "")

def normalize_api_url(api_url: str) -> str:
    # GUI 文本框容易夹带换行/空格；这里移除所有空白字符，避免请求变形/被重定向到首页 HTML
    return "".join((api_url or "").split())

def maybe_convert_web_url_to_api_url(input_url: str) -> str:
    """
    允许用户传入前端页面 URL（含 #/datasets/dataView?...），自动转换为 API URL。
    规则：
    - 若已包含 /api/ 认为是 API URL，直接返回
    - 否则尝试从 query 中提取 datasetId/dataset_id 作为 dataset_id
    """
    input_url = normalize_api_url(input_url)
    if not input_url:
        return input_url
    if "/api/" in input_url:
        return input_url

    parsed = urlparse(input_url)
    # 前端路由一般在 fragment 里：#/datasets/dataView?...
    fragment = parsed.fragment or ""
    frag_query = ""
    if "?" in fragment:
        frag_query = fragment.split("?", 1)[1]

    # 兼容：有些链接直接放在 query 里
    qs = parse_qs(parsed.query)
    if frag_query:
        frag_qs = parse_qs(frag_query)
        # fragment 参数覆盖 query
        qs = {**qs, **frag_qs}

    dataset_id = None
    for key in ("dataset_id", "datasetId", "enhanceDatasetId"):
        vals = qs.get(key)
        if vals and str(vals[0]).strip():
            dataset_id = str(vals[0]).strip()
            break

    if not dataset_id:
        return input_url

    sort_type = (qs.get("sort_type") or qs.get("sortType") or ["m_time"])[0]
    fuzzy_name = (qs.get("fuzzy_name") or qs.get("fuzzyName") or [""])[0]

    # 默认参数保持与之前脚本一致
    return (
        f"{DEFAULT_DATASET_ITEMS_PAGE_URL}"
        f"?limit=10000000&skip=0&annotation_status=labeled"
        f"&sort_type={sort_type}&fuzzy_name={fuzzy_name}"
        f"&dataset_id={dataset_id}&annotator_id=0"
    )

def extract_query_params_from_url(input_url: str) -> Dict[str, List[str]]:
    """
    从 URL 的 query + fragment(query) 中抽取参数字典（兼容 #/...?... 的前端路由）。
    """
    input_url = normalize_api_url(input_url)
    if not input_url:
        return {}

    parsed = urlparse(input_url)
    fragment = parsed.fragment or ""
    frag_query = ""
    if "?" in fragment:
        frag_query = fragment.split("?", 1)[1]

    qs = parse_qs(parsed.query)
    if frag_query:
        frag_qs = parse_qs(frag_query)
        qs = {**qs, **frag_qs}
    return qs

def extract_approach_id_from_url(input_url: str) -> Optional[int]:
    qs = extract_query_params_from_url(input_url)
    for key in ("approach_id", "approachId", "approachID"):
        vals = qs.get(key)
        if vals and str(vals[0]).strip():
            try:
                return int(str(vals[0]).strip())
            except Exception:
                return None
    return None

def fetch_labels_map(approach_id: int, access_token: str, labels_url: str = DEFAULT_LABELS_URL) -> Dict[int, Dict[str, Any]]:
    """
    拉取某个 approach_id 下的所有 labels。
    返回: {label_id: {"name": label_name, "color": label_color}}
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "Origin": "https://www.ai.magic-fox.com",
        "Referer": "https://www.ai.magic-fox.com/",
    }
    resp = requests.get(labels_url, headers=headers, params={"approach_id": approach_id}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200 or not data.get("success"):
        raise Exception(f"labels 接口返回错误: {data.get('msg', '未知错误')}")

    items = data.get("data") or []
    out: Dict[int, Dict[str, Any]] = {}
    if isinstance(items, list):
        for it in items:
            if not isinstance(it, dict):
                continue
            try:
                lid = int(it.get("id"))
            except Exception:
                continue
            name = it.get("label_name") or it.get("name") or ""
            color = it.get("label_color") or it.get("color")
            if isinstance(name, str) and name.strip():
                out[lid] = {"name": name.strip(), "color": color}
    return out


@dataclass(frozen=True)
class ExportOptions:
    api_url: str
    access_token: str
    output_dir: str = "./coco_dataset"

    # 下载配置
    download_files_url: str = DEFAULT_DOWNLOAD_FILES_URL
    download_images: bool = False
    download_names: Optional[Set[str]] = None  # 仅下载指定 file_name 的图片
    images_subdir: str = "images"
    download_batch_size: int = 200
    download_timeout_sec: int = 60
    download_retries: int = 2
    # True：将 COCO 标注写入 output_dir/images_subdir/_annotations.coco.json（与图片文件同级）
    annotations_in_images_subdir: bool = False


def fetch_data(api_url: str, access_token: str) -> List[Dict[str, Any]]:
    """从 API 获取数据（dataset_items/page）"""
    print("正在从 API 获取数据...")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    try:
        api_url = maybe_convert_web_url_to_api_url(api_url)
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()

        if not response.content:
            raise Exception(f"API 响应为空（status={response.status_code}）")

        try:
            data = response.json()
        except (ValueError, RequestsJSONDecodeError) as e:
            ct = response.headers.get("Content-Type", "")
            final_url = getattr(response, "url", api_url)
            redirects = " -> ".join([h.url for h in (response.history or [])] + [final_url])
            text_preview = (response.text or "")[:800]
            raise Exception(
                "API 返回内容不是有效 JSON。"
                f"\n- status: {response.status_code}"
                f"\n- final_url: {final_url}"
                f"\n- redirects: {redirects}"
                f"\n- content-type: {ct}"
                f"\n- body前800字符: {text_preview}"
                "\n\n提示：你传入的 api_url 可能是网页地址（带 #/...），请改用 API："
                f"\n{DEFAULT_DATASET_ITEMS_PAGE_URL}?limit=...&skip=...&dataset_id=...&annotator_id=..."
            ) from e

        if data.get("code") == 200 and data.get("success"):
            total_count = data["data"]["total_count"]
            print(f"成功获取数据，共 {total_count} 条记录")
            return data["data"]["dataset_items"]
        raise Exception(f"API 返回错误: {data.get('msg', '未知错误')}")
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        raise

def safe_json_parse(json_str, field_name):
    """安全解析 JSON 字符串"""
    try:
        return json.loads(json_str) if json_str else {}
    except json.JSONDecodeError as e:
        print(f"解析 {field_name} 失败: {e}")
        return {}


def normalize_magic_fox_bbox_to_coco_xywh(
    x: Any, y: Any, w: Any, h: Any
) -> Tuple[List[int], float]:
    """
    将平台 shape.points 中的 x,y,w,h 规范为 COCO 的 [x_min, y_min, width, height]。
    线上偶发 w/h 为负（两点顺序或方向不一致）；用 min/max 得到轴对齐框与正宽高。
    若归一化后某边为 0（退化线/点），抬到 1px，避免下游假设 w,h>0 时崩溃。
    """
    try:
        xf = float(x)
        yf = float(y)
        wf = float(w)
        hf = float(h)
    except (TypeError, ValueError):
        xf = yf = wf = hf = 0.0
    x1 = min(xf, xf + wf)
    x2 = max(xf, xf + wf)
    y1 = min(yf, yf + hf)
    y2 = max(yf, yf + hf)
    nw = int(round(x2 - x1))
    nh = int(round(y2 - y1))
    if nw < 1:
        nw = 1
    if nh < 1:
        nh = 1
    ix = int(round(x1))
    iy = int(round(y1))
    return [ix, iy, nw, nh], float(nw * nh)


def fix_coco_annotations_bboxes_inplace(coco_data: Dict[str, Any]) -> int:
    """
    就地修正已有 COCO dict 中 annotations 的 bbox（负宽高 → 正宽高）并同步 area。
    仅在规范化后的 bbox 与磁盘上原值不一致时改写（避免误动仅 area 浮点与 w*h 略有差异的历史文件）。
    """
    n = 0
    for ann in coco_data.get("annotations") or []:
        if not isinstance(ann, dict):
            continue
        bb = ann.get("bbox")
        if not isinstance(bb, (list, tuple)) or len(bb) != 4:
            continue
        new_bb, new_area = normalize_magic_fox_bbox_to_coco_xywh(*bb)
        old_t = tuple(int(round(float(x))) for x in bb)
        if tuple(new_bb) != old_t:
            ann["bbox"] = new_bb
            ann["area"] = new_area
            n += 1
    return n

def _find_label_name_in_obj(obj: Any, target_label_id: Any) -> Optional[str]:
    """
    在 annotations 的任意嵌套结构里，尝试找到某个 label_id 对应的 label_name/name。
    兼容常见结构：
    - {"label_id": 4403, "label_name": "..."}
    - {"id": 4403, "name": "..."}
    - {"id": "4403", "name": "..."}
    """
    try:
        target_int = int(target_label_id)
    except Exception:
        target_int = None

    def _match_id(v: Any) -> bool:
        if v is None:
            return False
        if target_int is not None:
            try:
                return int(v) == target_int
            except Exception:
                return False
        return v == target_label_id

    stack = [obj]
    seen = set()
    while stack:
        cur = stack.pop()
        if id(cur) in seen:
            continue
        seen.add(id(cur))

        if isinstance(cur, dict):
            # 结构 1：label_id + label_name
            if "label_id" in cur and ("label_name" in cur or "name" in cur):
                if _match_id(cur.get("label_id")):
                    name = cur.get("label_name") or cur.get("name")
                    if isinstance(name, str) and name.strip():
                        return name.strip()
            # 结构 2：id + name
            if "id" in cur and ("name" in cur or "label_name" in cur):
                if _match_id(cur.get("id")):
                    name = cur.get("name") or cur.get("label_name")
                    if isinstance(name, str) and name.strip():
                        return name.strip()

            # 继续遍历子节点
            for v in cur.values():
                if isinstance(v, (dict, list)):
                    stack.append(v)
        elif isinstance(cur, list):
            for v in cur:
                if isinstance(v, (dict, list)):
                    stack.append(v)

    return None

def extract_categories_from_annotations(
    dataset_items: List[Dict[str, Any]],
    label_definitions: Optional[Dict[int, Dict[str, Any]]] = None,
):
    """
    从 annotations 字段中的 shapes 里提取类别信息
    每个 shape 包含 label_id 和 label_name
    """
    category_info = {}  # {label_id: {"name": label_name, "color": label_color}}

    for item in dataset_items:
        if not item.get("annotations"):
            continue

        annotations = safe_json_parse(item["annotations"], "annotations")
        if not annotations or "shapes" not in annotations:
            continue

        for shape in annotations["shapes"]:
            # 仅统计真正会导出的 bbox 类别（避免把非 bbox 或无 points 的 shape 计入 categories）
            if shape.get("type") != "bounding_box" or not shape.get("points"):
                continue
            label_id = shape.get("label_id")
            label_name = shape.get("label_name")
            label_color = shape.get("label_color")

            # 注意：label_id 可能为 0，因此不能用 `if label_id`
            # 部分 shape 可能缺少 label_name，但 label_id 仍然有效；此时用兜底名称避免后续“未知类别”刷屏
            if label_id is None:
                continue

            # 优先级：
            # 1) labels 接口定义（最权威）
            # 2) shape 内 label_name
            # 3) annotations 其它字段递归搜
            # 4) unknown_*
            name = None
            norm_id = None
            try:
                norm_id = int(label_id)
            except Exception:
                norm_id = None

            if norm_id is not None and label_definitions and norm_id in label_definitions:
                name = label_definitions[norm_id].get("name")
                if not label_color:
                    label_color = label_definitions[norm_id].get("color")

            if not name:
                if isinstance(label_name, str) and label_name.strip():
                    name = label_name.strip()
                else:
                    found = _find_label_name_in_obj(annotations, label_id)
                    if found:
                        name = found
            if not name:
                name = f"unknown_{label_id}"

            if label_id not in category_info:
                category_info[label_id] = {"name": name, "color": label_color}
            else:
                # 如果之前是 unknown_*, 后续又拿到了真实 label_name，则补全
                if (
                    category_info[label_id].get("name", "").startswith("unknown_")
                    and isinstance(name, str)
                    and not name.startswith("unknown_")
                ):
                    category_info[label_id]["name"] = name
                # 颜色优先用非空值
                if not category_info[label_id].get("color") and label_color:
                    category_info[label_id]["color"] = label_color

    # 将原始 label_id 重新映射为从 0 开始的连续 id
    # label_id 可能是 str/int，统一转成 int 用于排序与映射
    normalized_info = {}
    for raw_id, info in category_info.items():
        try:
            norm_id = int(raw_id)
        except (TypeError, ValueError):
            # 极端情况下无法转 int，则退化为使用原值本身（保持稳定）
            norm_id = raw_id
        normalized_info[norm_id] = info

    sorted_old_ids = sorted(normalized_info.keys())
    old_to_new = {old_id: new_id for new_id, old_id in enumerate(sorted_old_ids)}

    # 构建 categories 列表（使用新 id）
    categories = []
    for old_id in sorted_old_ids:
        info = normalized_info[old_id]
        new_id = old_to_new[old_id]
        category = {
            "id": new_id,
            "name": info["name"],
            "supercategory": "none",
            "color": info.get("color"),  # 保留颜色信息作为扩展字段
            "original_id": old_id        # 额外保留原始 label_id 便于追溯
        }
        categories.append(category)

    print(f"从数据中发现 {len(categories)} 个类别（已重新映射为从0开始）:")
    for cat in categories:
        print(f"  - 新ID: {cat['id']}, 原ID: {cat.get('original_id')}, 名称: {cat['name']}, 颜色: {cat.get('color')}")

    return categories, old_to_new

def convert_to_coco(
    dataset_items: List[Dict[str, Any]],
    label_definitions: Optional[Dict[int, Dict[str, Any]]] = None,
):
    """转换为 COCO 格式"""
    print("\n开始转换为 COCO 格式...")

    # 从 annotations 中提取类别信息
    categories, old_to_new_category_id = extract_categories_from_annotations(dataset_items, label_definitions)

    # COCO 基本结构
    coco_data = {
        "info": {
            "year": datetime.now().year,
            "version": "1.0",
            "description": "Converted from Magic-Fox dataset",
            "date_created": datetime.now().isoformat()
        },
        "licenses": [
            {
                "id": 1,
                "name": "Unknown",
                "url": ""
            }
        ],
        "images": [],
        "annotations": [],
        "categories": categories
    }

    annotation_id = 1
    processed_count = 0
    skipped_count = 0
    category_stats = defaultdict(int)
    unknown_category_stats = defaultdict(int)  # {old_cat_id: skipped_count}

    # 遍历每个数据项
    for item_idx, item in enumerate(dataset_items, 1):
        try:
            # 解析 annotations
            annotations = safe_json_parse(item.get("annotations", "{}"), "annotations")
            shapes = (annotations or {}).get("shapes") or []

            # 解析 labels（用于验证）
            labels = safe_json_parse(item.get("labels", "{}"), "labels")

            meta = (annotations or {}).get("meta", {}) or {}

            # 获取图片尺寸
            width = meta.get("width", 0)
            height = meta.get("height", 0)

            if width == 0 or height == 0:
                print(f"警告: 图片 {item.get('object_name')} 尺寸信息不完整，跳过")
                skipped_count += 1
                continue

            # 添加图片信息
            image_id = item["id"]
            coco_data["images"].append({
                "id": image_id,
                "width": width,
                "height": height,
                "file_name": item.get("object_name", ""),
                "license": 1,
                "date_captured": item.get("c_time", ""),
                # 保留原始数据作为参考
                "original_labels": labels,
                "original_object_key": item.get("object_key"),
                "split_type": item.get("split_type"),
                "annotation_status": item.get("annotation_status")
            })

            # 没有任何框：仍然保留图片，但不产生 annotations
            if not shapes:
                processed_count += 1
                if processed_count % 100 == 0:
                    print(f"已处理 {processed_count} 张图片...")
                continue

            # 验证 labels 与实际 shapes 数量是否匹配
            actual_counts = defaultdict(int)
            for shape in shapes:
                if "label_id" in shape:
                    actual_counts[shape["label_id"]] += 1

            if labels:
                for label_id, expected_count in labels.items():
                    label_id = int(label_id)
                    actual_count = actual_counts.get(label_id, 0)
                    if actual_count != expected_count:
                        print(f"警告: 图片 {item.get('object_name')} 中类别 {label_id} 的标注数量不一致: "
                              f"labels={expected_count}, 实际={actual_count}")

            # 添加每个标注
            for shape in shapes:
                if shape.get("type") != "bounding_box" or not shape.get("points"):
                    continue

                point = shape["points"][0]

                # 确保类别存在，并将原始 label_id 映射到从 0 开始的新 id
                try:
                    old_cat_id = int(shape["label_id"])
                except (TypeError, ValueError):
                    old_cat_id = shape["label_id"]

                if old_cat_id not in old_to_new_category_id:
                    # 不刷屏：汇总后统一提示（通常是 shape 缺 label_name 导致类别未被提取）
                    unknown_category_stats[old_cat_id] += 1
                    continue
                new_cat_id = old_to_new_category_id[old_cat_id]

                # COCO 格式的 bbox 是 [x, y, width, height]（正宽高；平台可能给负 w/h）
                bbox, area = normalize_magic_fox_bbox_to_coco_xywh(
                    point.get("x"),
                    point.get("y"),
                    point.get("w"),
                    point.get("h"),
                )

                coco_data["annotations"].append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": new_cat_id,
                    "bbox": bbox,
                    "area": area,
                    "segmentation": [],
                    "iscrowd": 0,
                    "ignore": 0,
                    # 保留原始信息
                    "source": shape.get("source"),
                    "transcription": shape.get("transcription")
                })

                annotation_id += 1
                category_stats[new_cat_id] += 1

            processed_count += 1
            if processed_count % 100 == 0:
                print(f"已处理 {processed_count} 张图片...")

        except Exception as e:
            print(f"处理图片 {item.get('object_name', '未知')} 时出错: {e}")
            skipped_count += 1

    print(f"\n转换完成:")
    print(f"- 成功处理: {processed_count} 张图片")
    print(f"- 跳过: {skipped_count} 张图片")
    print(f"- 生成标注: {len(coco_data['annotations'])} 个")
    print(f"- 类别数: {len(coco_data['categories'])}")
    if unknown_category_stats:
        top = sorted(unknown_category_stats.items(), key=lambda x: x[1], reverse=True)[:10]
        preview = ", ".join([f"{k}({v})" for k, v in top])
        print(f"- 未识别类别（已跳过标注）: {len(unknown_category_stats)} 个，Top10: {preview}")

    return coco_data, category_stats

def fetch_download_urls(
    download_files_url: str,
    access_token: str,
    object_keys: Sequence[str],
) -> Dict[str, str]:
    """通过 download_files 接口，将对象 key 批量换取临时下载 URL"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        # 该接口在服务端会读取来源域名；缺少时可能触发服务端异常
        "Origin": "https://www.ai.magic-fox.com",
        "Referer": "https://www.ai.magic-fox.com/",
    }

    resp = requests.post(download_files_url, headers=headers, json=list(object_keys), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 200 or not data.get("success"):
        raise Exception(f"download_files 接口返回错误: {data.get('msg', '未知错误')}")
    return (((data.get("data") or {}).get("urls")) or {})


def download_images_for_coco(coco_data: Dict[str, Any], opts: ExportOptions) -> Path:
    """下载 COCO images 对应的图片到本地 images 目录（支持断点续跑）"""
    output_dir = Path(opts.output_dir)
    images_dir = output_dir / opts.images_subdir
    images_dir.mkdir(parents=True, exist_ok=True)

    # 需要下载的对象：[(object_key, local_path)]
    needed: List[Tuple[str, Path]] = []
    for img in coco_data.get("images", []):
        object_key = img.get("original_object_key")
        file_name = img.get("file_name") or ""
        if not object_key or not file_name:
            continue
        if opts.download_names is not None and file_name not in opts.download_names:
            continue
        local_path = images_dir / file_name
        if local_path.exists() and local_path.stat().st_size > 0:
            continue
        needed.append((object_key, local_path))

    print(f"\n开始下载图片: 目标目录={images_dir}，待下载={len(needed)}")
    if not needed:
        return images_dir

    batch_size = int(opts.download_batch_size)
    timeout_sec = int(opts.download_timeout_sec)
    retries = int(opts.download_retries)

    downloaded = 0
    failed = 0

    for start in range(0, len(needed), batch_size):
        batch = needed[start:start + batch_size]
        keys = [k for k, _ in batch]

        print(f"获取下载URL: {start}-{start + len(batch) - 1} / {len(needed)}（batch_size={batch_size}）")
        try:
            urls_map = fetch_download_urls(opts.download_files_url, opts.access_token, keys)
        except Exception as e:
            print(f"❌ 获取下载URL失败（batch {start}-{start+len(batch)-1}）: {e}")
            failed += len(batch)
            continue

        for object_key, local_path in batch:
            url = urls_map.get(object_key)
            if not url:
                print(f"⚠️ 该对象未返回URL，将跳过: {object_key}")
                failed += 1
                continue

            ok = False
            for attempt in range(retries + 1):
                try:
                    with requests.get(url, stream=True, timeout=timeout_sec) as r:
                        r.raise_for_status()
                        tmp_path = local_path.with_suffix(local_path.suffix + ".tmp")
                        with open(tmp_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        os.replace(tmp_path, local_path)
                    ok = True
                    break
                except Exception as e:
                    if attempt >= retries:
                        print(f"❌ 下载失败: {local_path.name}（{object_key}）: {e}")
                    continue

            if ok:
                downloaded += 1
            else:
                failed += 1

            total_done = downloaded + failed
            if total_done % 100 == 0:
                print(f"已下载进度: 成功={downloaded}, 失败={failed}, 总计处理={total_done}/{len(needed)}")

        # 每个 batch 结束也打印一次，避免长时间无输出
        print(f"batch完成: 成功={downloaded}, 失败={failed}, 总计处理={downloaded + failed}/{len(needed)}")

    print(f"图片下载完成: 成功={downloaded}, 失败={failed}, 目录={images_dir}")
    return images_dir

def save_coco_file(coco_data, filename="annotations.json"):
    """保存 COCO 文件"""
    output_dir = Path(filename).parent if os.path.isabs(filename) else None
    if output_dir is None or str(output_dir) == ".":
        output_dir = Path(".")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = Path(filename) if os.path.isabs(filename) else (output_dir / filename)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ COCO 文件已保存到: {output_path}")
    return output_path

def generate_stats(coco_data, category_stats):
    """生成统计信息"""
    # 构建类别名称映射
    category_names = {cat["id"]: cat["name"] for cat in coco_data["categories"]}

    stats = {
        "total_images": len(coco_data["images"]),
        "total_annotations": len(coco_data["annotations"]),
        "categories": {},
        "split_distribution": defaultdict(int),
        "images_with_labels": 0
    }

    # 统计每个类别的标注数量
    for cat_id, count in category_stats.items():
        cat_name = category_names.get(cat_id, f"未知_{cat_id}")
        stats["categories"][cat_name] = {
            "id": cat_id,
            "count": count
        }

    # 统计数据集划分
    for img in coco_data["images"]:
        split_type = img.get("split_type", "unknown")
        stats["split_distribution"][split_type] += 1

        if img.get("original_labels"):
            stats["images_with_labels"] += 1

    # 转换为普通字典
    stats["split_distribution"] = dict(stats["split_distribution"])

    return stats

def parse_download_names(value: Optional[str]) -> Optional[Set[str]]:
    """
    支持三种形式：
    - 逗号分隔：a.jpg,b.jpg
    - txt：每行一个文件名
    - json：["a.jpg","b.jpg"] 或 {"names":["a.jpg",...]}
    """
    if not value:
        return None

    p = Path(value)
    if p.exists() and p.is_file():
        text = p.read_text(encoding="utf-8").strip()
        if not text:
            return set()
        if p.suffix.lower() == ".json":
            obj = json.loads(text)
            if isinstance(obj, list):
                return {str(x) for x in obj}
            if isinstance(obj, dict) and isinstance(obj.get("names"), list):
                return {str(x) for x in obj["names"]}
            raise ValueError("download_names json 格式仅支持 list 或 {'names':[...]} ")
        # txt / 其他：按行读
        return {line.strip() for line in text.splitlines() if line.strip()}

    # 不存在文件：按逗号分隔
    return {x.strip() for x in value.split(",") if x.strip()}


def export_magicfox_to_coco(
    api_url: str,
    access_token: Optional[str] = None,
    output_dir: str = "./coco_dataset",
    *,
    annotations_name: str = "annotations.json",
    stats_name: str = "stats.json",
    approach_id: Optional[int] = None,
    download_images: bool = False,
    download_names: Optional[Iterable[str]] = None,
    subset_file_names: Optional[Iterable[str]] = None,
    download_files_url: str = DEFAULT_DOWNLOAD_FILES_URL,
    images_subdir: str = "images",
    download_batch_size: int = 200,
    download_timeout_sec: int = 60,
    download_retries: int = 2,
    annotations_in_images_subdir: bool = False,
    verbose: bool = True,
) -> Dict[str, Any]:
    """
    完整封装：拉取 Magic-Fox 标注数据 -> 转 COCO -> 写入 output_dir

    - download_images=False：不下载图片
    - download_images=True 且 download_names=None：下载全部图片
    - download_names 非空：仅下载指定 file_name（不依赖 download_images 开关）
    - subset_file_names 非空：仅将 object_name 在该集合内的条目参与转换（COCO 与下载范围均为子集，避免整库 JSON）
    - annotations_in_images_subdir=True：标注文件写在 output_dir/images_subdir/ 下（与图片同级），否则写在 output_dir/
    """
    token = normalize_access_token(
        access_token
        if access_token is not None
        else (os.getenv("MAGIC_FOX_ACCESS_TOKEN") or os.getenv("MAGIC_FOX_TOKEN") or "")
    )
    if not token:
        raise ValueError("access_token 为空：请传参 access_token 或设置环境变量 MAGIC_FOX_ACCESS_TOKEN")

    names_set: Optional[Set[str]] = None
    if download_names is not None:
        names_set = {str(x) for x in download_names}

    opts = ExportOptions(
        api_url=maybe_convert_web_url_to_api_url(api_url),
        access_token=token,
        output_dir=output_dir,
        download_files_url=download_files_url,
        download_images=download_images,
        download_names=names_set,
        images_subdir=images_subdir,
        download_batch_size=download_batch_size,
        download_timeout_sec=download_timeout_sec,
        download_retries=download_retries,
        annotations_in_images_subdir=annotations_in_images_subdir,
    )

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    out_cm = contextlib.nullcontext()
    err_cm = contextlib.nullcontext()
    if not verbose:
        out_cm = contextlib.redirect_stdout(stdout_buf)
        err_cm = contextlib.redirect_stderr(stderr_buf)

    with out_cm, err_cm:
        print("🚀 开始 COCO 数据集转换流程...")
        print("=" * 50)

        # 0) 获取 labels 定义（用于补全类别名称）
        label_definitions: Optional[Dict[int, Dict[str, Any]]] = None
        effective_approach_id = approach_id if approach_id is not None else extract_approach_id_from_url(api_url)
        if effective_approach_id is not None:
            try:
                label_definitions = fetch_labels_map(effective_approach_id, opts.access_token)
                print(f"已获取 labels: approach_id={effective_approach_id}, 数量={len(label_definitions)}")
            except Exception as e:
                print(f"⚠️ 获取 labels 失败（将继续用 shapes 内信息兜底）: {e}")
        else:
            print("未从 api_url 解析到 approach_id，将仅使用 shapes 内的 label_name/兜底逻辑。")

        start_time = time.time()
        dataset_items = fetch_data(opts.api_url, opts.access_token)
        print(f"⏱️  数据获取耗时: {time.time() - start_time:.2f}秒")
        if not dataset_items:
            raise Exception("没有获取到数据")

        if subset_file_names is not None:
            subset_set = {str(x).strip() for x in subset_file_names if str(x).strip()}
            if subset_set:
                n0 = len(dataset_items)
                dataset_items = [
                    it
                    for it in dataset_items
                    if str(it.get("object_name", "") or "").strip() in subset_set
                ]
                print(
                    f"subset_file_names: 按 {len(subset_set)} 个文件名过滤记录，"
                    f"{n0} -> {len(dataset_items)} 条"
                )
                if not dataset_items:
                    raise Exception(
                        "subset_file_names 过滤后无数据：文件名须与线上 object_name 一致；"
                        "请核对 exported 里 COCO 的 file_name 与表「图片名」是否完全相同。"
                    )

        convert_start_time = time.time()
        coco_data, category_stats = convert_to_coco(dataset_items, label_definitions)
        print(f"⏱️  转换耗时: {time.time() - convert_start_time:.2f}秒")

        out_dir = Path(opts.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        annotations_name = str(annotations_name).strip() or "annotations.json"
        if not annotations_name.lower().endswith(".json"):
            annotations_name = f"{annotations_name}.json"
        if opts.annotations_in_images_subdir:
            ann_dir = out_dir / opts.images_subdir
            ann_dir.mkdir(parents=True, exist_ok=True)
            annotations_path = ann_dir / annotations_name
        else:
            annotations_path = out_dir / annotations_name
        with open(annotations_path, "w", encoding="utf-8") as f:
            json.dump(coco_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ COCO 文件已保存到: {annotations_path}")

        # 下载图片：download_names 指定时强制下载指定列表；否则由 download_images 决定是否全量下载
        should_download = (opts.download_names is not None) or bool(opts.download_images)
        if should_download:
            download_images_for_coco(coco_data, opts)

        stats = generate_stats(coco_data, category_stats)
        stats_name = str(stats_name).strip() or "stats.json"
        if not stats_name.lower().endswith(".json"):
            stats_name = f"{stats_name}.json"
        stats_path = out_dir / stats_name
        with open(stats_path, "w", encoding="utf-8") as f:
            json.dump(stats, f, ensure_ascii=False, indent=2)
        print(f"📊 统计信息已保存到: {stats_path}")

        print("\n✨ 转换完成！")
        print(f"📁 输出目录: {out_dir.absolute()}")

    result = {
        "output_dir": str(out_dir),
        "annotations_path": str(annotations_path),
        "stats_path": str(stats_path),
        "downloaded_images_dir": str((out_dir / opts.images_subdir).absolute()),
        "stats": stats,
    }
    if not verbose:
        result["logs_stdout"] = stdout_buf.getvalue()
        result["logs_stderr"] = stderr_buf.getvalue()
    return result


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Magic-Fox -> COCO 导出（可选下载图片）")
    p.add_argument(
        "--api-url",
        required=True,
        help="dataset_items/page 的完整 API URL；也支持粘贴网页 dataView 链接（会自动转换）",
    )
    p.add_argument("--approach-id", type=int, default=None, help="可选：显式指定 approach_id（用于拉 labels 补全类别名）")
    p.add_argument(
        "--access-token",
        default=None,
        help="Bearer token；不传则读取环境变量 MAGIC_FOX_ACCESS_TOKEN 或 MAGIC_FOX_TOKEN",
    )
    p.add_argument("--output-dir", default="./coco_dataset", help="输出目录")
    p.add_argument("--annotations-name", default="_annotations.coco.json", help="导出的 COCO 标注 JSON 文件名（默认 _annotations.coco.json）")
    p.add_argument(
        "--annotations-in-images-dir",
        action="store_true",
        help="将标注 JSON 写入 images 子目录（与图片文件同级），默认关闭（写在 output-dir 根目录）",
    )
    p.add_argument("--stats-name", default="stats.json", help="导出的统计 JSON 文件名（默认 stats.json）")
    p.add_argument("--download-images", action="store_true", help="下载全部图片到 output_dir/images")
    p.add_argument(
        "--subset-names",
        default=None,
        help="仅转换/导出 COCO 中 object_name 在该列表内的条目：逗号分隔或 txt/json 文件路径（同 --download-names 规则）",
    )
    p.add_argument(
        "--download-names",
        default=None,
        help="仅下载指定文件名：'a.jpg,b.jpg' 或传 txt/json 文件路径",
    )
    p.add_argument("--download-files-url", default=DEFAULT_DOWNLOAD_FILES_URL, help="download_files 接口 URL")
    p.add_argument("--images-subdir", default="images", help="图片子目录名")
    p.add_argument("--download-batch-size", type=int, default=200, help="每次换取 URL 的 key 数")
    p.add_argument("--download-timeout-sec", type=int, default=60, help="单张图片下载超时（秒）")
    p.add_argument("--download-retries", type=int, default=2, help="单张图片下载重试次数")
    return p


def _token_from_skill_or_script_roots() -> str:
    """Skill 包内：在 scripts/ 或 Skill 根目录查找 .token（与 magic-fox-model-validation 约定一致）。"""
    d = Path(__file__).resolve().parent
    roots: List[Path] = [d, d.parent]
    if d.name == "scripts":
        roots.append(d.parent)
    for r in roots:
        p = r / ".token"
        if p.exists():
            return normalize_access_token(p.read_text(encoding="utf-8"))
    return ""


def _resolve_access_token(cli_token: Optional[str]) -> Optional[str]:
    if cli_token:
        t = normalize_access_token(cli_token)
        return t if t else None
    t = normalize_access_token(
        os.getenv("MAGIC_FOX_ACCESS_TOKEN") or os.getenv("MAGIC_FOX_TOKEN") or ""
    )
    if t:
        return t
    t = _token_from_skill_or_script_roots()
    return t if t else None


# 供 mf_dataset_download 等模块导入
resolve_magic_fox_access_token = _resolve_access_token


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = build_arg_parser().parse_args(argv)
    access = _resolve_access_token(args.access_token)
    names = parse_download_names(args.download_names)
    subset = parse_download_names(args.subset_names)
    export_magicfox_to_coco(
        api_url=args.api_url,
        access_token=access,
        output_dir=args.output_dir,
        annotations_name=args.annotations_name,
        stats_name=args.stats_name,
        approach_id=args.approach_id,
        download_images=bool(args.download_images),
        download_names=names,
        subset_file_names=subset,
        download_files_url=args.download_files_url,
        images_subdir=args.images_subdir,
        download_batch_size=args.download_batch_size,
        download_timeout_sec=args.download_timeout_sec,
        download_retries=args.download_retries,
        annotations_in_images_subdir=bool(args.annotations_in_images_dir),
    )


if __name__ == "__main__":
    main()
