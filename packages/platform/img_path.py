"""图片路径解析（查询与质检共用）。"""
from __future__ import annotations

import os


def img_path_from_object_key(object_key: str, *, img_base_path: str | None = None) -> str:
    if not object_key:
        return ''
    if img_base_path is None:
        from server.core import DEFAULT_CONFIG, load_config
        config = load_config()
        img_base_path = str(config.get('img_base_path') or DEFAULT_CONFIG['img_base_path'] or '').strip()
    base = str(img_base_path or '').strip()
    if base and not base.endswith(('/', '\\')):
        base += '/'
    return base + str(object_key)


def normalize_existing_path(path: str) -> str:
    """返回磁盘上真实存在的路径；Windows 上尝试 E:/D: 盘符互换。"""
    path = str(path or '').strip()
    if not path:
        return ''
    if os.path.isfile(path):
        return path
    if os.name == 'nt' and len(path) >= 2 and path[1] == ':':
        drive = path[0].upper()
        rest = path[2:].lstrip('\\/')
        for alt_drive in ('E', 'D', 'C'):
            if alt_drive == drive:
                continue
            alt = f'{alt_drive}:/{rest}'.replace('/', '\\')
            if os.path.isfile(alt):
                return alt
    return path


def resolve_detail_img_path(row: dict) -> str:
    """解析平台明细图绝对路径：优先 local_pic_url，其次 origin_object_key 拼接。"""
    row = dict(row or {})
    local_pic = str(row.get('local_pic_url') or '').strip()
    if local_pic:
        path = normalize_existing_path(local_pic.replace('\\', '/'))
        if path:
            return path
    ok = str(row.get('origin_object_key') or '').strip()
    if ok:
        path = normalize_existing_path(img_path_from_object_key(ok))
        if path:
            return path
    return local_pic or img_path_from_object_key(ok) or ''


def apply_img_paths(df):
    """根据配置为 DataFrame 添加 img_path 列（委托 server.core，统一入口）。"""
    from server.core import apply_img_paths as _core_apply
    return _core_apply(df)
