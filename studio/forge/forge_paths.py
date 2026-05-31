"""路径安全：限制图片读取与导出写入只能落在白名单根目录内，
防止 `?path=` 任意文件读取与 `out_dir` 任意目录写入。
"""
import os

from studio.paths import PROJECT_ROOT as BASE_DIR


def _abs(p):
    return os.path.abspath(os.path.realpath(str(p)))


def is_within(path, roots):
    """path 是否落在任一允许根目录之内（含根目录本身）。"""
    if not path:
        return False
    rp = _abs(path)
    for root in roots:
        if not root:
            continue
        root = _abs(root)
        try:
            if os.path.commonpath([rp, root]) == root:
                return True
        except ValueError:
            continue  # 不同盘符（Windows）
    return False


def allowed_read_roots():
    """允许通过 /api/image 读取的根目录。"""
    from server.core import load_config, DEFAULT_CONFIG
    cfg = load_config()
    roots = [
        os.path.join(BASE_DIR, 'uploads'),
        os.path.join(BASE_DIR, 'exports'),
        os.path.join(BASE_DIR, 'datasets'),
    ]
    img_base = str(cfg.get('img_base_path') or DEFAULT_CONFIG.get('img_base_path') or '').strip()
    if img_base:
        roots.append(img_base)
    for r in (cfg.get('allowed_image_roots') or []):
        if str(r).strip():
            roots.append(str(r).strip())
    for r in (cfg.get('dataset_sync_roots') or []):
        if str(r).strip():
            roots.append(str(r).strip())
    sync_root = str(cfg.get('dataset_sync_root') or '').strip()
    if sync_root:
        roots.append(sync_root if os.path.isabs(sync_root) else os.path.join(BASE_DIR, sync_root))
    return roots


def allowed_sync_roots():
    """允许数据集同步读写的根目录。"""
    from server.core import load_config
    cfg = load_config()
    roots = [
        os.path.join(BASE_DIR, 'datasets'),
        os.path.join(BASE_DIR, 'exports'),
    ]
    sync_root = str(cfg.get('dataset_sync_root') or 'datasets').strip()
    if sync_root:
        roots.append(sync_root if os.path.isabs(sync_root) else os.path.join(BASE_DIR, sync_root))
    for r in (cfg.get('dataset_sync_roots') or []):
        if str(r).strip():
            roots.append(str(r).strip())
    for r in (cfg.get('allowed_image_roots') or []):
        if str(r).strip():
            roots.append(str(r).strip())
    return roots


def safe_sync_dir(path):
    return is_within(path, allowed_sync_roots())


def safe_read_path(path):
    return is_within(path, allowed_read_roots())


def allowed_export_roots():
    """允许导出写入的根目录（默认仅 exports/，可经 manual_qc_export_roots 扩展）。"""
    from server.core import load_config
    cfg = load_config()
    roots = [os.path.join(BASE_DIR, 'exports')]
    for r in (cfg.get('manual_qc_export_roots') or []):
        if str(r).strip():
            roots.append(str(r).strip())
    return roots


def safe_export_dir(path):
    return is_within(path, allowed_export_roots())
