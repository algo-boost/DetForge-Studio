"""样本图库：标注写入 .coco/ 沙箱，图片直接指向原路径（不复制 .viz）。"""
from __future__ import annotations

import json
import os
import shutil
from copy import deepcopy

from studio.export.pred_coco_layout import remove_pred_sidecars
from studio.export.task_images import align_coco_to_original_paths

VIZ_SUBDIR = '.viz'       # 历史沙箱目录，打开看图时不再写入
COCO_SUBDIR = '.coco'     # 看图专用 COCO（不写回产线）
MAIN_COCO_NAME = '_annotations.coco.json'
TASK_COCO_NAME = MAIN_COCO_NAME  # 查询/导出用的主文件，仍在 export 根目录


def should_use_viz_workspace(export_dir: str) -> bool:
    """查询任务 / 预测作业导出目录使用分目录映射；训练集等直连路径不走。"""
    d = os.path.abspath(export_dir or '')
    if not d or not os.path.isdir(d):
        return False
    if os.path.isfile(os.path.join(d, 'result.csv')) or os.path.isfile(os.path.join(d, 'query_meta.json')):
        return True
    parent = os.path.basename(os.path.dirname(d))
    base = os.path.basename(d)
    return parent == 'exports' and base.startswith('predict_job_')


def _viz_coco_path(export_dir: str) -> str:
    return os.path.join(export_dir, COCO_SUBDIR, MAIN_COCO_NAME)


def clean_stale_coco_artifacts(export_dir: str) -> int:
    """
    清理查询目录内陈旧 COCO 产物。
    保留 export 根目录主 COCO（导出 ZIP 用）；删除侧车、.viz/.coco 内旧文件。
    """
    export_dir = os.path.abspath(export_dir)
    if not os.path.isdir(export_dir):
        return 0
    removed = remove_pred_sidecars(export_dir)
    try:
        for name in os.listdir(export_dir):
            if name in (VIZ_SUBDIR, COCO_SUBDIR):
                continue
            if name == TASK_COCO_NAME:
                continue
            if not name.startswith('_annotations.') or not name.endswith('.json'):
                continue
            path = os.path.join(export_dir, name)
            if os.path.isfile(path):
                os.remove(path)
                removed += 1
    except OSError:
        pass
    for sub in (VIZ_SUBDIR, COCO_SUBDIR):
        subdir = os.path.join(export_dir, sub)
        if not os.path.isdir(subdir):
            continue
        removed += remove_pred_sidecars(subdir)
        stray = os.path.join(subdir, MAIN_COCO_NAME)
        if sub == VIZ_SUBDIR and os.path.isfile(stray):
            try:
                os.remove(stray)
                removed += 1
            except OSError:
                pass
    return removed


def _strip_source_fields(coco: dict) -> dict:
    """去掉会触发 COCOVisualizer 回写产线 GT 的字段。"""
    out = deepcopy(coco or {})
    out.pop('source_dirs', None)
    out.pop('source_coco_paths', None)
    for img in out.get('images') or []:
        if isinstance(img, dict):
            img.pop('source_path', None)
    return out


def _filter_coco_by_indices(coco: dict, selected_indices) -> dict:
    if not selected_indices:
        return coco
    sel = {int(i) for i in selected_indices}
    out = deepcopy(coco)
    out['images'] = [
        img for img in (out.get('images') or [])
        if int(img.get('id', -1)) in sel
    ]
    out['annotations'] = [
        ann for ann in (out.get('annotations') or [])
        if int(ann.get('image_id', -1)) in sel
    ]
    return out


def _prepare_predict_coco(export_dir: str) -> None:
    """在 export 根目录主 COCO 上补齐预测框（导出/归档仍用该文件）。"""
    meta_path = os.path.join(export_dir, 'query_meta.json')
    if not os.path.isfile(meta_path):
        return
    try:
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
    except Exception:
        return
    if meta.get('data_source') != 'predict_result':
        return
    from studio.export.pred_coco_layout import prepare_predict_task_for_viz
    prep = prepare_predict_task_for_viz(export_dir)
    if prep.get('annotation_count', 0) == 0:
        raise ValueError(
            '预测结果无可用标注框，样本图库无法显示目标框。'
            '请确认筛选后 ext 仍含预测框，或重新执行查询。'
        )


def _reset_viz_coco_dir(export_dir: str) -> None:
    coco_path = os.path.join(export_dir, COCO_SUBDIR)
    if os.path.isdir(coco_path):
        shutil.rmtree(coco_path)
    os.makedirs(coco_path, exist_ok=True)
    # 清理历史 .viz 副本目录（已不再使用）
    viz_path = os.path.join(export_dir, VIZ_SUBDIR)
    if os.path.isdir(viz_path):
        shutil.rmtree(viz_path, ignore_errors=True)


def _viz_coco_up_to_date(export_dir: str, *, selected_indices=None) -> bool:
    """`.coco` 已存在且比任务主 COCO / CSV 新时跳过重建。"""
    if selected_indices:
        return False
    export_dir = os.path.abspath(export_dir)
    viz_path = _viz_coco_path(export_dir)
    task_coco = os.path.join(export_dir, TASK_COCO_NAME)
    if not os.path.isfile(viz_path) or not os.path.isfile(task_coco):
        return False
    try:
        viz_m = os.path.getmtime(viz_path)
        if os.path.getmtime(task_coco) > viz_m:
            return False
        for name in ('result.csv', 'query_meta.json'):
            dep = os.path.join(export_dir, name)
            if os.path.isfile(dep) and os.path.getmtime(dep) > viz_m:
                return False
        return True
    except OSError:
        return False


def prepare_export_dir_for_viz(export_dir: str, *, selected_indices=None) -> tuple[str, str]:
    """
    打开样本图库前的准备（不改变 COCOVisualizer API）。

    - 主 COCO 仍在 export 根目录（供导出 ZIP）
    - 看图 COCO：``.coco/_annotations.coco.json``，images[].file_name 为**原图绝对路径**
    - 不复制图片；ensure_viz_dataset 的 image_dir 传任务目录作兜底

    返回 (coco_json_path, image_dir)。
    """
    export_dir = os.path.abspath(export_dir)
    task_coco_path = os.path.join(export_dir, TASK_COCO_NAME)
    if not os.path.isfile(task_coco_path):
        raise FileNotFoundError(f'COCO 文件不存在: {task_coco_path}')

    if _viz_coco_up_to_date(export_dir, selected_indices=selected_indices):
        return _viz_coco_path(export_dir), export_dir

    clean_stale_coco_artifacts(export_dir)
    _prepare_predict_coco(export_dir)
    _reset_viz_coco_dir(export_dir)

    with open(task_coco_path, 'r', encoding='utf-8') as f:
        coco = json.load(f)
    coco = _strip_source_fields(coco)
    coco = _filter_coco_by_indices(coco, selected_indices)

    n = align_coco_to_original_paths(export_dir, coco, selected_indices)
    if n == 0:
        raise ValueError(
            '查询结果无可用图片，无法打开样本图库。'
            '请确认 result.csv 中 img_path 在本机可访问（预测结果需为服务器绝对路径，'
            '或检测明细已配置正确的 img_base_path）。'
        )

    viz_coco_path = _viz_coco_path(export_dir)
    with open(viz_coco_path, 'w', encoding='utf-8') as f:
        json.dump(coco, f, ensure_ascii=False, separators=(',', ':'))

    return viz_coco_path, export_dir


def build_viz_workspace(export_dir: str, *, selected_indices=None) -> tuple[str, str]:
    return prepare_export_dir_for_viz(export_dir, selected_indices=selected_indices)
