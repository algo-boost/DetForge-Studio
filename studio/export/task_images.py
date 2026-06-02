"""查询任务目录内图片路径解析（导出 ZIP / 归档）。"""
import os
import re

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')


def _is_image_file(name):
    return str(name or '').lower().endswith(IMAGE_EXTENSIONS)


def resolve_task_image_path(task_dir, image_id, *, coco_file_name=None, csv_img_path=None):
    """
    解析 task 目录中的图片文件。

    build_query_task 复制为 ``{image_id}_{basename}``；COCO/CSV 可能仍是 basename 或绝对路径。
    返回 (绝对路径, zip/归档用相对文件名)；找不到时 (None, None)。
    """
    task_dir = os.path.abspath(task_dir or '')
    if not task_dir or not os.path.isdir(task_dir):
        return None, None

    try:
        iid = int(image_id)
    except (TypeError, ValueError):
        return None, None

    candidates = []

    def add(path, arcname=None):
        if not path:
            return
        path = os.path.abspath(path)
        if os.path.isfile(path):
            candidates.append((path, arcname or os.path.basename(path)))

    fn = str(coco_file_name or '').strip()
    if fn:
        if os.path.isabs(fn):
            add(fn)
        else:
            add(os.path.join(task_dir, fn), fn.replace('\\', '/'))
            add(os.path.join(task_dir, os.path.basename(fn)), os.path.basename(fn).replace('\\', '/'))

    csv_path = str(csv_img_path or '').strip()
    if csv_path:
        base = os.path.basename(csv_path)
        prefixed = f'{iid}_{base}'
        add(os.path.join(task_dir, prefixed), prefixed)
        add(os.path.join(task_dir, base), base)
        if os.path.isabs(csv_path):
            add(csv_path, prefixed)

    prefix = f'{iid}_'
    try:
        for name in os.listdir(task_dir):
            if name.startswith(prefix) and _is_image_file(name):
                add(os.path.join(task_dir, name), name)
    except OSError:
        pass

    seen = set()
    for path, arc in candidates:
        key = (path, arc)
        if key in seen:
            continue
        seen.add(key)
        return path, arc.replace('\\', '/')

    return None, None


def normalize_coco_images_for_task(task_dir, coco_data, selected_indices=None):
    """
    为导出/归档对齐 images[].file_name，并返回 [(src_path, arcname), ...]。
    """
    images = list((coco_data or {}).get('images') or [])
    if selected_indices is not None:
        sel = {int(i) for i in selected_indices}
        images = [img for img in images if int(img.get('id', -1)) in sel]

    csv_by_id = {}
    csv_path = os.path.join(task_dir, 'result.csv')
    if os.path.isfile(csv_path):
        try:
            import pandas as pd
            df = pd.read_csv(csv_path, encoding='utf-8')
            for idx, row in df.iterrows():
                p = row.get('img_path', '')
                if p is not None and not (isinstance(p, float) and pd.isna(p)):
                    csv_by_id[int(idx)] = str(p)
        except Exception:
            pass

    files = []
    for img in images:
        try:
            iid = int(img.get('id'))
        except (TypeError, ValueError):
            continue
        src, arc = resolve_task_image_path(
            task_dir,
            iid,
            coco_file_name=img.get('file_name'),
            csv_img_path=csv_by_id.get(iid),
        )
        if not src:
            continue
        img['file_name'] = arc
        files.append((src, arc))
    return files
