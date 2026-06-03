"""预测结果 COCO：默认预测框写入主 _annotations.coco.json；可选 pred 侧车（旧版/对比）。"""
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


def _rebuild_defect_categories(coco: dict, id2name_map: dict, defect_names: set, *, defect_check=None) -> None:
    """categories 仅保留缺陷词表且标注中实际出现的类。"""
    id_to_name = {int(k): str(v) for k, v in id2name_map.items()}
    name_to_id = {v: k for k, v in id_to_name.items()}
    used_names = set()
    kept_anns = []
    for ann in coco.get('annotations') or []:
        if not isinstance(ann, dict):
            continue
        name = str(ann.get('category') or id_to_name.get(int(ann.get('category_id', -1)), '')).strip()
        if not name:
            continue
        if defect_check is not None:
            if not defect_check(name):
                continue
        elif defect_names and name not in defect_names:
            continue
        kept_anns.append(ann)
        used_names.add(name)
    coco['annotations'] = kept_anns
    if used_names:
        coco['categories'] = [
            {'id': int(name_to_id[n]), 'name': n}
            for n in sorted(used_names)
            if n in name_to_id
        ]
    else:
        coco['categories'] = [
            {'id': int(k), 'name': v}
            for k, v in sorted(id2name_map.items())
            if not defect_names or v in defect_names
        ]


def build_predict_view_coco(
    rows,
    *,
    export_dir: str,
    model_name: str,
    id2name=None,
    info_meta=None,
    image_id_key='id',
    abs_file_name=False,
    merge_nearby_gt=False,
    defect_only=True,
    emit_pred_sidecar=False,
):
    """
    构建主 COCO；预测框默认写入主文件 annotations（样本图库单 GT 层即可见框）。
    rows: predict_result 行或带 img_path/ext 的 dict 列表。
    merge_nearby_gt: 是否合并图片目录旁产线 GT（默认关，避免总成类污染 categories）。
    emit_pred_sidecar: 为 True 时额外写 _annotations.<model>.pred.coco.json（对比看图用）。
    返回 (gt_coco_path, pred_coco_path|None, image_count, source_gt_paths)
    """
    from studio.export.csv2coco import DEFAULT_ID2NAME, build_coco_info
    from studio.export.annotation_parser import parse_row_predictions
    from studio.query.defect_categories import (
        DEFAULT_FALLBACK_CATEGORIES,
        _labels_for_defect_detection_source,
        defect_name_set,
        filter_id2name_map,
        is_defect_category_name,
    )

    id2name = id2name or DEFAULT_ID2NAME
    defect_cats = None
    if defect_only:
        try:
            from server.core import get_defect_categories_bundle
            bundle = get_defect_categories_bundle()
            raw_cats = bundle.get('categories') or []
            defect_cats = _labels_for_defect_detection_source(
                raw_cats, DEFAULT_FALLBACK_CATEGORIES,
            ) or list(DEFAULT_FALLBACK_CATEGORIES)
            id2name = filter_id2name_map(
                id2name or bundle.get('id2name') or DEFAULT_ID2NAME,
                categories=None,
            )
        except Exception:
            defect_cats = list(DEFAULT_FALLBACK_CATEGORIES)
            id2name = filter_id2name_map(id2name, categories=None)
    id2name_map, name2id = build_name2id_maps(id2name)
    defect_names = defect_name_set(categories=defect_cats, id2name=id2name_map) if defect_only else None
    defect_check = (
        (lambda n: is_defect_category_name(n, categories=defect_cats, id2name=id2name_map))
        if defect_only else None
    )
    gt_categories = [{'id': k, 'name': v} for k, v in sorted(id2name_map.items())]

    gt_coco = {
        'info': build_coco_info(info_meta or {}),
        'images': [],
        'categories': gt_categories,
        'annotations': [],
        'source_dirs': {},
        'source_coco_paths': {},
    }
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
        stored_fname = abs_path if abs_file_name else basename
        img_dir = os.path.dirname(abs_path)

        img_info = {
            'id': image_id,
            'file_name': stored_fname,
            'width': row.get('img_width'),
            'height': row.get('img_height'),
            'product_no': row.get('product_no'),
            'product_type': row.get('product_type'),
            'product_id': row.get('product_id'),
            'position': row.get('position'),
        }
        img_info = {k: v for k, v in img_info.items() if v is not None and v != ''}
        gt_coco['images'].append(img_info)

        if merge_nearby_gt:
            gt_coco.setdefault('source_dirs', {})[img_dir] = img_dir
            gt_data, gt_path = find_nearby_gt_coco(abs_path)
            if gt_data and gt_path:
                source_gt_paths[img_dir] = gt_path
                src_cats = _gt_categories(gt_data)
                merge_gt_categories(gt_coco['categories'], src_cats)
                gt_anns = _gt_annotations_for_image(gt_data, basename, image_id)
                remap_gt_annotation_category_ids(gt_anns, src_cats, gt_coco['categories'])
                gt_coco['annotations'].extend(gt_anns)

        preds = parse_row_predictions(row)
        pred_annotations.extend(
            predictions_to_coco_annotations(
                image_id,
                preds,
                name2id,
                id2name_map,
                gt_categories,
                defect_only=defect_only,
                defect_check=defect_check,
            )
        )

    if not gt_coco['images']:
        raise ValueError('预测结果原图均不可用，无法打开样本图库')

    if source_gt_paths:
        gt_coco['source_coco_paths'] = source_gt_paths

    if pred_annotations:
        gt_coco['annotations'].extend(pred_annotations)
        _assign_annotation_ids(gt_coco['annotations'])

    if defect_only and defect_names:
        _rebuild_defect_categories(gt_coco, id2name_map, defect_names, defect_check=defect_check)

    os.makedirs(export_dir, exist_ok=True)
    remove_pred_sidecars(export_dir)
    gt_path = os.path.join(export_dir, '_annotations.coco.json')
    with open(gt_path, 'w', encoding='utf-8') as f:
        json.dump(gt_coco, f, ensure_ascii=False, indent=2)

    pred_path = None
    if emit_pred_sidecar and pred_annotations:
        slug = sanitize_model_slug(model_name)
        pred_images = [
            {
                'id': int(img['id']),
                'file_name': img.get('file_name'),
                'width': img.get('width'),
                'height': img.get('height'),
            }
            for img in gt_coco['images']
            if img.get('id') is not None
        ]
        pred_path = write_pred_sidecar(
            export_dir, slug, pred_images, deepcopy(gt_categories), deepcopy(pred_annotations),
        )

    return gt_path, pred_path, len(gt_coco['images']), source_gt_paths


def _merge_categories(target_categories: list[dict], extra_categories: list[dict]) -> None:
    known_ids = {int(c.get('id')) for c in target_categories if c.get('id') is not None}
    known_names = {c.get('name') for c in target_categories if c.get('name')}
    next_id = max(known_ids, default=-1) + 1
    for cat in extra_categories or []:
        if not isinstance(cat, dict):
            continue
        name = cat.get('name')
        if name and name in known_names:
            continue
        cid = cat.get('id')
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            cid = next_id
            next_id += 1
        if cid in known_ids:
            cid = next_id
            next_id += 1
        target_categories.append({'id': cid, 'name': name or f'class_{cid}'})
        known_ids.add(cid)
        if name:
            known_names.add(name)


def _assign_annotation_ids(annotations: list[dict], start_id: int = 1) -> int:
    next_id = start_id
    for ann in annotations or []:
        if not isinstance(ann, dict):
            continue
        if ann.get('id') is None:
            ann['id'] = next_id
            next_id += 1
        else:
            try:
                next_id = max(next_id, int(ann['id']) + 1)
            except (TypeError, ValueError):
                pass
    return next_id


def merge_pred_sidecars_into_coco(coco_data: dict, export_dir: str) -> dict:
    """将 predict 侧车 annotations 合并进主 COCO，供查询结果 ZIP 导出含预测框。"""
    if not coco_data or not export_dir or not os.path.isdir(export_dir):
        return coco_data

    out = dict(coco_data)
    categories = [dict(c) for c in (out.get('categories') or []) if isinstance(c, dict)]
    annotations = [dict(a) for a in (out.get('annotations') or []) if isinstance(a, dict)]
    pred_ann_count = 0

    for name in sorted(os.listdir(export_dir)):
        if not name.startswith('_annotations.') or '.pred.coco.json' not in name:
            continue
        path = os.path.join(export_dir, name)
        try:
            with open(path, 'r', encoding='utf-8') as f:
                pred_coco = json.load(f)
        except Exception:
            continue
        _merge_categories(categories, pred_coco.get('categories') or [])
        for ann in pred_coco.get('annotations') or []:
            if not isinstance(ann, dict):
                continue
            bbox = ann.get('bbox') or []
            if len(bbox) < 4:
                continue
            annotations.append(dict(ann))
            pred_ann_count += 1

    if pred_ann_count:
        _assign_annotation_ids(annotations)
        info = dict(out.get('info') or {})
        info['predict_annotations_merged'] = pred_ann_count
        out['info'] = info
    out['categories'] = categories
    out['annotations'] = annotations
    return out


def append_predictions_from_result_csv(coco_data: dict, csv_path: str, *, id2name=None) -> dict:
    """侧车缺失时从 result.csv 的 ext 列重建预测框并写入主 COCO。"""
    if not coco_data or not csv_path or not os.path.isfile(csv_path):
        return coco_data
    import pandas as pd
    from studio.export.annotation_parser import parse_row_predictions, predictions_to_coco_annotations, build_name2id_maps
    from studio.export.csv2coco import DEFAULT_ID2NAME
    from studio.query.defect_categories import (
        defect_name_set,
        filter_id2name_map,
        is_defect_category_name,
    )

    df = pd.read_csv(csv_path, encoding='utf-8')
    from studio.query.defect_categories import (
        DEFAULT_FALLBACK_CATEGORIES,
        _labels_for_defect_detection_source,
    )

    defect_cats = list(DEFAULT_FALLBACK_CATEGORIES)
    raw_id2name = id2name or DEFAULT_ID2NAME
    try:
        from server.core import get_defect_categories_bundle
        bundle = get_defect_categories_bundle()
        raw_cats = bundle.get('categories') or []
        trusted = _labels_for_defect_detection_source(raw_cats, DEFAULT_FALLBACK_CATEGORIES)
        if trusted:
            defect_cats = trusted
        raw_id2name = filter_id2name_map(
            raw_id2name or bundle.get('id2name') or DEFAULT_ID2NAME,
            categories=None,
        )
    except Exception:
        raw_id2name = filter_id2name_map(raw_id2name, categories=None)
    id2name_map, name2id = build_name2id_maps(raw_id2name)
    defect_names = defect_name_set(categories=defect_cats, id2name=id2name_map)
    defect_check = (
        (lambda n: is_defect_category_name(n, categories=defect_cats, id2name=id2name_map))
        if defect_names else None
    )
    out = dict(coco_data)
    categories = [dict(c) for c in (out.get('categories') or []) if isinstance(c, dict)]
    annotations = [dict(a) for a in (out.get('annotations') or []) if isinstance(a, dict)]
    image_ids = {int(img.get('id')) for img in (out.get('images') or []) if img.get('id') is not None}
    added = 0

    for idx, row in df.iterrows():
        try:
            image_id = int(idx)
        except (TypeError, ValueError):
            continue
        if image_ids and image_id not in image_ids:
            continue
        rec = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        preds = parse_row_predictions(rec)
        if not preds:
            continue
        new_anns = predictions_to_coco_annotations(
            image_id,
            preds,
            name2id,
            id2name_map,
            categories,
            defect_only=bool(defect_names),
            defect_check=defect_check,
        )
        annotations.extend(new_anns)
        added += len(new_anns)

    if added:
        _assign_annotation_ids(annotations)
        info = dict(out.get('info') or {})
        info['predict_annotations_from_csv'] = added
        out['info'] = info
    out['categories'] = categories
    out['annotations'] = annotations
    if defect_names:
        _rebuild_defect_categories(out, id2name_map, defect_names, defect_check=defect_check)
    return out


def ensure_predict_annotations_for_export(coco_data: dict, task_dir: str, *, id2name=None) -> dict:
    """预测结果任务导出/归档：主 COCO 合并侧车；无侧车则从 CSV 解析 ext；修剪类别。"""
    if not task_dir:
        return coco_data
    out = merge_pred_sidecars_into_coco(coco_data, task_dir)
    if not (out.get('annotations') or []):
        csv_path = os.path.join(task_dir, 'result.csv')
        out = append_predictions_from_result_csv(out, csv_path, id2name=id2name)
    try:
        from studio.export.annotation_parser import build_name2id_maps
        from studio.query.defect_categories import (
            DEFAULT_FALLBACK_CATEGORIES,
            _labels_for_defect_detection_source,
            defect_name_set,
            filter_id2name_map,
            is_defect_category_name,
        )
        from server.core import get_defect_categories_bundle

        bundle = get_defect_categories_bundle()
        raw_cats = bundle.get('categories') or []
        defect_cats = _labels_for_defect_detection_source(
            raw_cats, DEFAULT_FALLBACK_CATEGORIES,
        ) or list(DEFAULT_FALLBACK_CATEGORIES)
        filtered = filter_id2name_map(
            id2name or bundle.get('id2name') or {},
            categories=None,
        )
        id2name_map, _ = build_name2id_maps(filtered)
        defect_names = defect_name_set(categories=defect_cats, id2name=id2name_map)
        defect_check = lambda n: is_defect_category_name(n, categories=defect_cats, id2name=id2name_map)
        _rebuild_defect_categories(out, id2name_map, defect_names, defect_check=defect_check)
    except Exception:
        pass
    return out


def _task_image_id_to_filename(task_dir: str) -> dict[int, str]:
    """从主 COCO 读取 image.id → file_name（样本图库对齐用）。"""
    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        return {}
    try:
        with open(coco_path, 'r', encoding='utf-8') as f:
            gt = json.load(f)
    except Exception:
        return {}
    out = {}
    for img in gt.get('images') or []:
        try:
            iid = int(img.get('id'))
        except (TypeError, ValueError):
            continue
        fn = str(img.get('file_name') or '').strip()
        if fn:
            out[iid] = fn
    return out


def align_pred_sidecars_to_gt_images(task_dir: str) -> bool:
    """将 pred 侧车 images[].file_name 与主 COCO 对齐（修复 0_ 前缀不一致）。"""
    id_to_fname = _task_image_id_to_filename(task_dir)
    if not id_to_fname:
        return False
    changed = False
    for path in list_pred_sidecar_paths(task_dir):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                pred = json.load(f)
        except Exception:
            continue
        sidecar_changed = False
        for img in pred.get('images') or []:
            try:
                iid = int(img.get('id'))
            except (TypeError, ValueError):
                continue
            want = id_to_fname.get(iid)
            if want and img.get('file_name') != want:
                img['file_name'] = want
                sidecar_changed = True
        if sidecar_changed:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(pred, f, ensure_ascii=False, indent=2)
            changed = True
    return changed


def remove_pred_sidecars(export_dir: str) -> int:
    """删除目录内 pred 侧车，避免样本图库出现 GT+pred 双层（预测已入主 COCO）。"""
    removed = 0
    for path in list_pred_sidecar_paths(export_dir):
        try:
            os.remove(path)
            removed += 1
        except OSError:
            pass
    return removed


def rebuild_predict_coco_from_task(task_dir: str, *, id2name=None) -> str | None:
    """主 COCO 无标注时，从 result.csv 的 ext 重建（预测写入主文件，不写侧车）。"""
    csv_path = os.path.join(task_dir, 'result.csv')
    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if not os.path.isfile(csv_path):
        return None
    meta = {}
    meta_path = os.path.join(task_dir, 'query_meta.json')
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            meta = {}
    from studio.export.csv2coco import _csv2coco_predict_layout
    _csv2coco_predict_layout(csv_path, coco_path, id2name, meta)
    return coco_path if os.path.isfile(coco_path) else None


def _main_coco_annotation_count(task_dir: str) -> int:
    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        return 0
    try:
        with open(coco_path, 'r', encoding='utf-8') as f:
            return len((json.load(f).get('annotations')) or [])
    except Exception:
        return 0


def _annotations_from_main_coco(export_dir: str) -> dict[int, list[dict]]:
    """从主 COCO 读取 image_id → 预览用 annotations。"""
    coco_path = os.path.join(export_dir, '_annotations.coco.json')
    if not os.path.isfile(coco_path):
        return {}
    try:
        with open(coco_path, 'r', encoding='utf-8') as f:
            coco = json.load(f)
    except Exception:
        return {}
    cat_names = {
        int(c['id']): c.get('name', '')
        for c in (coco.get('categories') or [])
        if 'id' in c
    }
    out: dict[int, list[dict]] = {}
    for ann in coco.get('annotations') or []:
        try:
            iid = int(ann.get('image_id', -1))
        except (TypeError, ValueError):
            continue
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


def prepare_predict_task_for_viz(task_dir: str) -> dict:
    """
    打开样本图库前：旧侧车合并入主 COCO 后删除；主文件无框则从 CSV 重建。
    返回 {annotation_count, sidecars_removed}。
    """
    meta_path = os.path.join(task_dir, 'query_meta.json')
    meta = {}
    if os.path.isfile(meta_path):
        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        except Exception:
            pass
    if meta.get('data_source') != 'predict_result':
        return {'skipped': True}

    try:
        from server.core import get_effective_id2name
        id2name = get_effective_id2name()
    except Exception:
        id2name = None

    coco_path = os.path.join(task_dir, '_annotations.coco.json')
    if os.path.isfile(coco_path):
        try:
            with open(coco_path, 'r', encoding='utf-8') as f:
                coco = json.load(f)
            coco = ensure_predict_annotations_for_export(coco, task_dir, id2name=id2name)
            with open(coco_path, 'w', encoding='utf-8') as f:
                json.dump(coco, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    if _main_coco_annotation_count(task_dir) == 0:
        rebuild_predict_coco_from_task(task_dir, id2name=id2name)

    removed = remove_pred_sidecars(task_dir)

    return {
        'annotation_count': _main_coco_annotation_count(task_dir),
        'sidecars_removed': removed,
    }


def list_pred_sidecar_paths(export_dir: str) -> list[str]:
    if not export_dir or not os.path.isdir(export_dir):
        return []
    paths = []
    for name in sorted(os.listdir(export_dir)):
        if name.startswith('_annotations.') and name.endswith('.pred.coco.json'):
            paths.append(os.path.join(export_dir, name))
    return paths


def load_pred_annotations_by_image_id(export_dir: str) -> dict[int, list[dict]]:
    """读取预测标注：优先主 COCO；无则回退旧版 pred 侧车。"""
    if not export_dir or not os.path.isdir(export_dir):
        return {}
    out = _annotations_from_main_coco(export_dir)
    if out:
        return out

    out: dict[int, list[dict]] = {}
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
