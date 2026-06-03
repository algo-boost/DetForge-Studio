import os
import sys
import json
import shutil
import pandas as pd

from studio.export.annotation_parser import (
    build_name2id_maps,
    parse_row_predictions,
    predictions_to_coco_annotations,
    row_to_coco_image,
)

DEFAULT_ID2NAME = {
    0: '其他', 1: '划伤', 2: '压痕',
    3: '吊紧', 4: '异物外漏', 5: '折痕', 6: '抛线',
    7: '拼接间隙', 8: '水渍', 9: '烫伤', 10: '破损',
    11: '碰伤', 12: '红标签', 13: '线头', 14: '脏污',
    15: '褶皱(T型)', 16: '褶皱（重度）', 17: '重跳针',
}


def build_coco_info(query_meta=None):
    """构建 COCO info 元数据块。"""
    meta = query_meta or {}
    info = {
        'description': 'DefectLoop Studio export',
        'version': '1.0',
    }
    for key in (
        'query_sql', 'query_sql_executed', 'python_code', 'start_time', 'end_time',
        'strategy_id', 'strategy_name', 'sample_size', 'random_seed',
        'rows_before_sample', 'query_mode', 'filter_mode', 'post_sample_skipped',
    ):
        if meta.get(key) not in (None, ''):
            info[key] = meta.get(key)
    if meta.get('flow'):
        info['flow'] = meta['flow']
    return {k: v for k, v in info.items() if v is not None and v != ''}


def csv2coco(csv_file, coco_file, id2name=None, query_meta=None):
    """将 result.csv 导出为 COCO；预测结果表走 GT + pred 侧车布局。"""
    meta = query_meta or {}
    if meta.get('data_source') == 'predict_result':
        _csv2coco_predict_layout(csv_file, coco_file, id2name, meta)
        return

    if id2name is None:
        id2name = DEFAULT_ID2NAME

    id2name, name2id = build_name2id_maps(id2name)
    categories = [{'id': k, 'name': v} for k, v in sorted(id2name.items())]

    df = pd.read_csv(csv_file, encoding='utf-8')
    coco = {
        'info': build_coco_info(query_meta),
        'images': [],
        'categories': categories,
        'annotations': [],
    }

    for idx, row in df.iterrows():
        img_path = row.get('img_path')
        if pd.isna(img_path):
            continue
        image_info = row_to_coco_image(idx, row, img_path)
        if img_path and os.path.isfile(str(img_path)):
            try:
                from PIL import Image
                with Image.open(str(img_path)) as im:
                    image_info['width'], image_info['height'] = im.size
            except Exception:
                pass
        coco['images'].append(image_info)

        preds = parse_row_predictions(row)
        coco['annotations'].extend(
            predictions_to_coco_annotations(
                int(idx), preds, name2id, id2name, coco['categories'],
            )
        )

    with open(coco_file, 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, indent=4)


def _csv2coco_predict_layout(csv_file, coco_file, id2name, query_meta):
    from studio.export.pred_coco_layout import build_predict_view_coco

    df = pd.read_csv(csv_file, encoding='utf-8')
    export_dir = os.path.dirname(os.path.abspath(coco_file))
    model_name = query_meta.get('model_name') or 'predict'
    if 'model_name' in df.columns:
        series = df['model_name'].dropna()
        if len(series):
            model_name = str(series.iloc[0])

    rows = []
    for idx, row in df.iterrows():
        rec = {k: (None if pd.isna(v) else v) for k, v in row.items()}
        rec['_viz_id'] = int(idx)
        rows.append(rec)

    build_predict_view_coco(
        rows,
        export_dir=export_dir,
        model_name=model_name,
        id2name=id2name or DEFAULT_ID2NAME,
        info_meta=query_meta,
        image_id_key='_viz_id',
        abs_file_name=False,
    )


def _coco_file_name_for_export(target, base_dir):
    """COCO images[].file_name 仅存相对路径或文件名，不写磁盘绝对路径。"""
    target = os.path.abspath(target)
    base_dir = os.path.abspath(base_dir)
    try:
        rel = os.path.relpath(target, base_dir)
        if not rel.startswith('..') and not os.path.isabs(rel):
            return rel.replace('\\', '/')
    except ValueError:
        pass
    return os.path.basename(target)


def sync_coco_image_file_names(coco_path, image_paths_by_id, *, image_dir=None):
    """将 COCO images[].file_name 对齐到任务目录内相对路径或文件名（不含原图绝对路径）。

    image_paths_by_id: {image_id: 绝对路径}，通常为导出目录内 ``{idx}_{basename}``。
    """
    if not image_paths_by_id or not os.path.isfile(coco_path):
        return False
    with open(coco_path, 'r', encoding='utf-8') as f:
        coco = json.load(f)
    base_dir = os.path.abspath(image_dir) if image_dir else os.path.dirname(os.path.abspath(coco_path))
    changed = False
    for img in coco.get('images') or []:
        try:
            iid = int(img.get('id'))
        except (TypeError, ValueError):
            continue
        target = image_paths_by_id.get(iid)
        if not target or not os.path.isfile(target):
            continue
        target = os.path.abspath(target)
        new_name = _coco_file_name_for_export(target, base_dir)
        current = str(img.get('file_name') or '').strip()
        if current:
            cur_path = current if os.path.isabs(current) else os.path.join(base_dir, current)
            if os.path.isfile(cur_path) and not os.path.isabs(current) and current == new_name:
                continue
        if current != new_name:
            img['file_name'] = new_name
            changed = True
    if changed:
        with open(coco_path, 'w', encoding='utf-8') as f:
            json.dump(coco, f, ensure_ascii=False, indent=4)
    return changed


def copy_ng_images(coco_file, all_images_dir, ng_images_dir):
    os.makedirs(ng_images_dir, exist_ok=True)
    with open(coco_file, 'r', encoding='utf-8') as f:
        coco = json.load(f)
    for image in coco['images']:
        if image.get('check_status'):
            img_path = image.get('file_name')
            if img_path:
                shutil.copy(os.path.join(all_images_dir, img_path), os.path.join(ng_images_dir, img_path))
    shutil.copy(coco_file, os.path.join(ng_images_dir, '_annotations.coco.json'))


if __name__ == '__main__':
    csv_file = sys.argv[1]
    coco_file = sys.argv[2]
    csv2coco(csv_file, coco_file, DEFAULT_ID2NAME)
