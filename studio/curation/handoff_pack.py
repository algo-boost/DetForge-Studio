"""训练交接包：三场景统一目录结构与 COCO 构建。"""
from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime

from studio.curation.dispositions import (
    DISPOSITION_LABELS,
    INTENT_LABELS,
    disposition_from_qc_record,
    need_platform_label,
)
from studio.export.csv2coco import build_coco_info
from studio.paths import PROJECT_ROOT as BASE_DIR


def handoff_inbox_root():
    from server.core import load_config, DEFAULT_CONFIG
    cfg = load_config()
    root = str(cfg.get('handoff_root') or cfg.get('dataset_sync_root') or DEFAULT_CONFIG.get('dataset_sync_root') or 'datasets').strip()
    if not root:
        root = 'datasets'
    if not os.path.isabs(root):
        root = os.path.join(BASE_DIR, root)
    return os.path.join(root, 'training_inbox')


def write_handoff_readme(dest_dir, *, title, lines):
    body = '\n'.join([f'# {title}', ''] + lines + [''])
    with open(os.path.join(dest_dir, 'HANDOFF.md'), 'w', encoding='utf-8') as f:
        f.write(body)


def write_provenance(dest_dir, payload):
    with open(os.path.join(dest_dir, 'provenance.json'), 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_manifest_csv(dest_dir, rows, fieldnames):
    if not rows:
        return None
    path = os.path.join(dest_dir, 'manifest.csv')
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        w.writeheader()
        w.writerows(rows)
    return path


def _ext_predictions_to_coco_anns(ext, image_id, cat_map, ann_start=1):
    """platform ext → COCO annotations。"""
    anns = []
    if not ext:
        return anns, ann_start
    if isinstance(ext, str):
        try:
            ext = json.loads(ext)
        except (TypeError, ValueError):
            return anns, ann_start
    preds = []
    if isinstance(ext, dict):
        preds = ext.get('original_predictions') or ext.get('predictions') or []
    aid = ann_start
    for p in preds:
        if not isinstance(p, dict):
            continue
        name = str(p.get('name') or p.get('category') or 'defect')
        if name not in cat_map:
            cat_map[name] = len(cat_map) + 1
        cid = cat_map[name]
        pts = p.get('points') or []
        if pts and isinstance(pts[0], dict):
            pt = pts[0]
            x, y, w, h = pt.get('x', 0), pt.get('y', 0), pt.get('w', 0), pt.get('h', 0)
            bbox = [float(x), float(y), float(w), float(h)]
        else:
            bbox = p.get('bbox') or [0, 0, 0, 0]
        anns.append({
            'id': aid,
            'image_id': image_id,
            'category_id': cid,
            'bbox': bbox,
            'area': float(bbox[2] * bbox[3]) if len(bbox) >= 4 else 0,
            'iscrowd': 0,
            'score': float(p.get('confidence') or p.get('score') or 0),
        })
        aid += 1
    return anns, aid


def build_coco_from_manual_qc_records(records, *, use_platform=True):
    """从 manual_qc 记录构建 COCO（默认平台缺陷图 + 框）。"""
    images = []
    annotations = []
    cat_map = {}
    ann_id = 1
    for idx, r in enumerate(records):
        path = r.get('matched_img_path') if use_platform else r.get('customer_img_path')
        if not path:
            continue
        fname = os.path.basename(str(path))
        disp = disposition_from_qc_record(r)
        images.append({
            'id': idx,
            'file_name': fname,
            'extra': {
                'product_no': r.get('product_no'),
                'disposition': disp,
                'need_platform_label': need_platform_label(disp),
                'qc_category': r.get('qc_category'),
                'defect_type': r.get('defect_type'),
                'manual_qc_id': r.get('id'),
            },
        })
        ext = None
        info = r.get('defect_info')
        if isinstance(info, dict):
            ext = info.get('ext') or info
        elif isinstance(info, str):
            try:
                ext = json.loads(info)
            except (TypeError, ValueError):
                ext = None
        anns, ann_id = _ext_predictions_to_coco_anns(ext, idx, cat_map, ann_start=ann_id)
        annotations.extend(anns)
    categories = [{'id': cid, 'name': name} for name, cid in sorted(cat_map.items(), key=lambda x: x[1])]
    return {
        'info': build_coco_info({'purpose': 'manual_qc_handoff'}),
        'images': images,
        'annotations': annotations,
        'categories': categories,
    }


def assemble_handoff_dir(
    out_dir,
    *,
    intent_type,
    coco_data,
    image_copy_fn,
    manifest_rows,
    provenance_extra=None,
    readme_lines=None,
):
    """写入标准 handoff 目录。"""
    if os.path.exists(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    images_dir = os.path.join(out_dir, 'images')
    os.makedirs(images_dir, exist_ok=True)

    copied = 0
    if image_copy_fn:
        copied = int(image_copy_fn(images_dir) or 0)

    coco_path = os.path.join(out_dir, '_annotations.coco.json')
    with open(coco_path, 'w', encoding='utf-8') as f:
        json.dump(coco_data, f, ensure_ascii=False, indent=2)

    fields = list(manifest_rows[0].keys()) if manifest_rows else [
        'file_name', 'product_no', 'disposition', 'need_platform_label', 'source',
    ]
    write_manifest_csv(out_dir, manifest_rows, fields)

    prov = {
        'intent_type': intent_type,
        'intent_label': INTENT_LABELS.get(intent_type, intent_type),
        'handoff_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'image_count': len(coco_data.get('images') or []),
        'annotation_count': len(coco_data.get('annotations') or []),
    }
    if provenance_extra:
        prov.update(provenance_extra)
    write_provenance(out_dir, prov)

    write_handoff_readme(
        out_dir,
        title='训练交接包',
        lines=readme_lines or [
            f'- 场景：{INTENT_LABELS.get(intent_type, intent_type)}',
            f'- 目录：`{out_dir}`',
            '- 训练侧：手动导入 Magic-Fox 或拷贝至训练环境',
        ],
    )
    return {'out_dir': out_dir, 'images_copied': copied, 'coco_path': coco_path}
