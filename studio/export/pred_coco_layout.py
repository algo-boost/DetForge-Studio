"""COCOVisualizer 预测侧车：_annotations.<model>.pred.coco.json；GT 保留在主 COCO。"""
from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path

from studio.export.annotation_parser import (
    build_name2id_maps,
    predictions_to_coco_annotations,
)

_GT_CACHE: dict[str, dict] = {}


def sanitize_model_slug(name: str | None, fallback: str = 'predict') -> str:
    raw = str(name or '').strip() or fallback
    slug = re.sub(r'[^\w\-]+', '_', raw).strip('_')
    return (slug or fallback)[:64]


def pred_coco_filename(model_slug: str) -> str:
    return f'_annotations.{sanitize_model_slug(model_slug)}.pred.coco.json'


def _basename(file_name: str) -> str:
    return str(file_name or '').replace('\\', '/').split('/')[-1]


def load_gt_coco(coco_path: Path) -> dict | None:
    key = str(coco_path.resolve())
    if key in _GT_CACHE:
        return _GT_CACHE[key]
    try:
        with open(coco_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None
    _GT_CACHE[key] = data
    return data


def find_nearby_gt_coco(img_path: str) -> tuple[dict | None, str | None]:
    """从图片所在目录向上查找 _annotations.coco.json（GT 主文件）。"""
    if not img_path or not os.path.isfile(img_path):
        return None, None
    cur = Path(img_path).resolve().parent
    for _ in range(10):
        candidate = cur / '_annotations.coco.json'
        if candidate.is_file():
            data = load_gt_coco(candidate)
            if data is not None:
                return data, str(candidate.resolve())
        if cur.name in ('datasets', 'exports', 'uploads', 'DetForge-Studio') or cur.parent == cur:
            break
        cur = cur.parent
    return None, None


def _index_gt_images(gt_coco: dict) -> dict[str, dict]:
    out = {}
    for img in gt_coco.get('images') or []:
        base = _basename(img.get('file_name', ''))
        if base:
            out[base] = img
    return out


def _gt_categories(gt_coco: dict) -> list[dict]:
    return [dict(c) for c in (gt_coco.get('categories') or []) if isinstance(c, dict)]


def _gt_annotations_for_image(gt_coco: dict, basename: str, export_image_id: int) -> list[dict]:
    img_index = _index_gt_images(gt_coco)
    gt_img = img_index.get(basename)
    if not gt_img:
        return []
    gt_img_id = gt_img.get('id')
    anns = []
    for ann in gt_coco.get('annotations') or []:
        if ann.get('image_id') != gt_img_id:
            continue
        item = {k: v for k, v in ann.items() if not str(k).startswith('_')}
        item['image_id'] = export_image_id
        anns.append(item)
    return anns


def merge_gt_categories(target_categories: list[dict], gt_categories: list[dict]) -> None:
    known = {c.get('name'): c.get('id') for c in target_categories if c.get('name')}
    next_id = max((int(c.get('id', 0)) for c in target_categories), default=-1) + 1
    for cat in gt_categories:
        name = cat.get('name')
        if not name or name in known:
            continue
        cid = cat.get('id')
        if cid in {c.get('id') for c in target_categories}:
            cid = next_id
            next_id += 1
        target_categories.append({'id': int(cid), 'name': name})
        known[name] = cid


def remap_gt_annotation_category_ids(annotations: list[dict], gt_categories: list[dict], target_categories: list[dict]) -> None:
    gt_id_to_name = {int(c['id']): c['name'] for c in gt_categories if 'id' in c and c.get('name')}
    name_to_target_id = {c['name']: c['id'] for c in target_categories if c.get('name')}
    for ann in annotations:
        gt_name = gt_id_to_name.get(int(ann.get('category_id', -1)))
        if gt_name and gt_name in name_to_target_id:
            ann['category_id'] = name_to_target_id[gt_name]


def write_pred_sidecar(export_dir: str, model_slug: str, images: list[dict], categories: list[dict], annotations: list[dict]) -> str:
    """写入 _annotations.<model>.pred.coco.json，返回绝对路径。"""
    path = os.path.join(export_dir, pred_coco_filename(model_slug))
    payload = {
        'info': {'description': 'DefectLoop predict sidecar'},
        'images': images,
        'categories': categories,
        'annotations': annotations,
    }
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def build_predict_view_coco(
    rows,
    *,
    export_dir: str,
    model_name: str,
    id2name=None,
    info_meta=None,
    image_id_key='id',
    abs_file_name=True,
):
    """
    构建 GT 主 COCO + pred 侧车。
    rows: predict_result 行或带 img_path/ext 的 dict 列表。
    返回 (gt_coco_path, pred_coco_path|None, image_count, source_gt_paths)
    """
    from studio.export.csv2coco import DEFAULT_ID2NAME, build_coco_info
    from studio.export.annotation_parser import parse_row_predictions

    id2name = id2name or DEFAULT_ID2NAME
    id2name_map, name2id = build_name2id_maps(id2name)
    gt_categories = [{'id': k, 'name': v} for k, v in sorted(id2name_map.items())]
    pred_categories = deepcopy(gt_categories)

    gt_coco = {
        'info': build_coco_info(info_meta or {}),
        'images': [],
        'categories': gt_categories,
        'annotations': [],
        'source_dirs': {},
        'source_coco_paths': {},
    }
    pred_images = []
    pred_annotations = []
    source_gt_paths: dict[str, str] = {}

    for i, row in enumerate(rows):
        img_path = str(row.get('img_path') or '').strip()
        if not img_path or not os.path.isfile(img_path):
            continue
        if image_id_key and row.get(image_id_key) is not None:
            image_id = int(row[image_id_key])
        else:
            image_id = i
        abs_path = os.path.abspath(img_path)
        basename = os.path.basename(abs_path)
        img_dir = os.path.dirname(abs_path)
        gt_coco['source_dirs'][img_dir] = img_dir

        img_info = {
            'id': image_id,
            'file_name': abs_path if abs_file_name else basename,
            'source_path': img_dir,
            'width': row.get('img_width'),
            'height': row.get('img_height'),
            'product_no': row.get('product_no'),
            'product_type': row.get('product_type'),
            'product_id': row.get('product_id'),
            'position': row.get('position'),
        }
        img_info = {k: v for k, v in img_info.items() if v is not None and v != ''}
        gt_coco['images'].append(img_info)

        gt_data, gt_path = find_nearby_gt_coco(abs_path)
        if gt_data and gt_path:
            source_gt_paths[img_dir] = gt_path
            src_cats = _gt_categories(gt_data)
            merge_gt_categories(gt_coco['categories'], src_cats)
            gt_anns = _gt_annotations_for_image(gt_data, basename, image_id)
            remap_gt_annotation_category_ids(gt_anns, src_cats, gt_coco['categories'])
            gt_coco['annotations'].extend(gt_anns)

        preds = parse_row_predictions(row)
        pred_images.append({
            'id': image_id,
            'file_name': basename,
            'width': row.get('img_width'),
            'height': row.get('img_height'),
        })
        pred_annotations.extend(
            predictions_to_coco_annotations(
                image_id, preds, name2id, id2name_map, pred_categories,
            )
        )

    if not gt_coco['images']:
        raise ValueError('预测结果原图均不可用，无法打开样本图库')

    if source_gt_paths:
        gt_coco['source_coco_paths'] = source_gt_paths

    os.makedirs(export_dir, exist_ok=True)
    gt_path = os.path.join(export_dir, '_annotations.coco.json')
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt_coco, f, ensure_ascii=False, indent=2)

    pred_path = None
    if pred_annotations:
        slug = sanitize_model_slug(model_name)
        pred_path = write_pred_sidecar(export_dir, slug, pred_images, pred_categories, pred_annotations)

    return gt_path, pred_path, len(gt_coco['images']), source_gt_paths


def load_pred_annotations_by_image_id(export_dir: str) -> dict[int, list[dict]]:
    """读取目录内 pred 侧车，返回 image_id → API 结果 annotations 列表。"""
    out: dict[int, list[dict]] = {}
    if not export_dir or not os.path.isdir(export_dir):
        return out
    cat_names: dict[int, str] = {}
    for name in os.listdir(export_dir):
        if '.pred.coco.json' not in name or not name.startswith('_annotations.'):
            continue
        path = os.path.join(export_dir, name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                pred_coco = json.load(f)
        except Exception:
            continue
        cat_names = {int(c['id']): c.get('name', '') for c in pred_coco.get('categories') or [] if 'id' in c}
        for ann in pred_coco.get('annotations') or []:
            iid = int(ann.get('image_id', -1))
            bbox = ann.get('bbox') or []
            if iid < 0 or len(bbox) < 4:
                continue
            out.setdefault(iid, []).append({
                'bbox': bbox,
                'category': ann.get('category') or cat_names.get(int(ann.get('category_id', 0)), ''),
                'category_id': ann.get('category_id', 0),
                'score': ann.get('score', 0),
            })
    return out
