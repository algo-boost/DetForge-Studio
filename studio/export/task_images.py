"""查询任务目录内图片路径解析（导出 ZIP / 归档 / 样本图库）。"""
import os
import re
from functools import lru_cache

IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.webp')


def _is_image_file(name):
    return str(name or '').lower().endswith(IMAGE_EXTENSIONS)


def _basename_only(name):
    return str(name or '').replace('\\', '/').split('/')[-1]


def export_arcname(basename: str, image_id: int, used: set) -> str:
    """导出/归档 ZIP 内相对文件名：默认仅 basename；重名时用 ``{id}_{basename}``。"""
    base = _basename_only(basename)
    if not base:
        base = f'image_{image_id}.jpg'
    if base not in used:
        used.add(base)
        return base
    prefixed = f'{image_id}_{base}'
    used.add(prefixed)
    return prefixed


def expand_img_path(path):
    """将 CSV/库中的 img_path 解析为可访问的绝对路径（含 img_base_path 拼接）。"""
    p = str(path or '').strip()
    if not p or p.lower() == 'nan':
        return ''
    if os.path.isfile(p):
        return os.path.abspath(p)
    if os.path.isabs(p):
        return p
    try:
        from server.core import load_config
        base = str((load_config() or {}).get('img_base_path') or '').strip().rstrip('/\\')
        if base:
            cand = os.path.join(base, p.replace('/', os.sep).lstrip(os.sep))
            if os.path.isfile(cand):
                return os.path.abspath(cand)
    except Exception:
        pass
    return p


def _load_csv_paths_by_image_id(task_dir):
    """从 result.csv 构建 {coco image.id: 原图路径}。同时按行号与 id 列建索引。"""
    import csv

    csv_path = os.path.join(task_dir, 'result.csv')
    if not os.path.isfile(csv_path):
        return {}
    out = {}
    try:
        with open(csv_path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row_i, row in enumerate(reader):
                raw = (row.get('img_path') or '').strip()
                if not raw or raw.lower() == 'nan':
                    continue
                p = expand_img_path(raw) or raw
                out[row_i] = p
                rid = (row.get('id') or '').strip()
                if rid and rid.lower() != 'nan':
                    try:
                        out[int(float(rid))] = p
                    except (TypeError, ValueError):
                        pass
                viz_id = (row.get('_viz_id') or '').strip()
                if viz_id and viz_id.lower() != 'nan':
                    try:
                        out[int(float(viz_id))] = p
                    except (TypeError, ValueError):
                        pass
    except OSError:
        return {}
    return out


@lru_cache(maxsize=64)
def _legacy_prefixed_index(task_dir: str) -> dict[int, str]:
    """一次性扫描任务目录内遗留 ``{id}_{basename}`` 副本（避免每张图 listdir）。"""
    index: dict[int, str] = {}
    td = os.path.abspath(task_dir or '')
    if not td or not os.path.isdir(td):
        return index
    try:
        for name in os.listdir(td):
            m = re.match(r'^(\d+)_', name)
            if m and _is_image_file(name):
                index[int(m.group(1))] = os.path.join(td, name)
    except OSError:
        pass
    return index


def resolve_task_image_path(
    task_dir,
    image_id,
    *,
    coco_file_name=None,
    csv_img_path=None,
    legacy_by_id=None,
):
    """
    解析任务对应的原图或遗留副本。

    日常查询/预测不再复制到 task 目录；优先 result.csv / COCO 中的原图绝对路径。
    返回 (绝对路径, 导出用 arcname 基名)；找不到时 (None, None)。
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
            arc = arcname or _basename_only(path)
            candidates.append((path, arc.replace('\\', '/')))

    csv_path = expand_img_path(csv_img_path) if csv_img_path else ''
    if csv_path:
        add(csv_path, _basename_only(csv_path))

    fn = str(coco_file_name or '').strip()
    if fn:
        if os.path.isabs(fn) and os.path.isfile(fn):
            add(fn, _basename_only(fn))
        else:
            base = _basename_only(fn)
            if csv_path and os.path.isabs(csv_path):
                add(csv_path, base)
            add(os.path.join(task_dir, fn), base)
            add(os.path.join(task_dir, base), base)
            prefixed = f'{iid}_{base}'
            add(os.path.join(task_dir, prefixed), prefixed)

    if csv_path and not os.path.isabs(csv_path):
        base = _basename_only(csv_path)
        prefixed = f'{iid}_{base}'
        add(os.path.join(task_dir, prefixed), prefixed)
        add(os.path.join(task_dir, base), base)

    legacy = legacy_by_id if legacy_by_id is not None else _legacy_prefixed_index(task_dir)
    lp = legacy.get(iid)
    if lp:
        add(lp, os.path.basename(lp))

    seen = set()
    for path, arc in candidates:
        key = (path, arc)
        if key in seen:
            continue
        seen.add(key)
        return path, arc

    return None, None


def normalize_coco_images_for_task(task_dir, coco_data, selected_indices=None, *, for_export=False):
    """
    对齐 images[].file_name，并返回 [(src_path, arcname), ...]。

    for_export=True（ZIP/归档）：arcname 仅为文件名（重名加 id 前缀），并复制到同一目录。
    for_export=False（样本图库 .viz）：arcname 可与 COCO 一致，便于沙箱内打开。
    """
    images = list((coco_data or {}).get('images') or [])
    if selected_indices is not None:
        sel = {int(i) for i in selected_indices}
        images = [img for img in images if int(img.get('id', -1)) in sel]

    csv_by_id = _load_csv_paths_by_image_id(task_dir)
    legacy_by_id = _legacy_prefixed_index(os.path.abspath(task_dir))
    used_arc = set()
    files = []
    for img in images:
        try:
            iid = int(img.get('id'))
        except (TypeError, ValueError):
            continue
        src, _legacy_arc = resolve_task_image_path(
            task_dir,
            iid,
            coco_file_name=img.get('file_name'),
            csv_img_path=csv_by_id.get(iid),
            legacy_by_id=legacy_by_id,
        )
        if not src:
            continue
        base = _basename_only(src)
        if for_export:
            arc = export_arcname(base, iid, used_arc)
        else:
            arc = _legacy_arc or base
        img['file_name'] = arc
        files.append((src, arc))
    return files


def align_coco_to_original_paths(task_dir, coco_data, selected_indices=None) -> int:
    """
    样本图库：将 images[].file_name 设为原图绝对路径（COCOVisualizer 支持绝对 file_name）。
    返回成功对齐的图片数。
    """
    images = list((coco_data or {}).get('images') or [])
    if selected_indices is not None:
        sel = {int(i) for i in selected_indices}
        images = [img for img in images if int(img.get('id', -1)) in sel]

    csv_by_id = _load_csv_paths_by_image_id(task_dir)
    legacy_by_id = _legacy_prefixed_index(os.path.abspath(task_dir))
    count = 0
    for img in images:
        try:
            iid = int(img.get('id'))
        except (TypeError, ValueError):
            continue
        src, _ = resolve_task_image_path(
            task_dir,
            iid,
            coco_file_name=img.get('file_name'),
            csv_img_path=csv_by_id.get(iid),
            legacy_by_id=legacy_by_id,
        )
        if not src:
            continue
        img['file_name'] = os.path.abspath(src).replace('\\', '/')
        count += 1
    return count
