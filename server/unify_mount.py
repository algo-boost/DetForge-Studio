"""DetUnify-Studio 同进程挂载：/unify 前缀 Web UI + API。"""
from __future__ import annotations

import importlib.util
import os
import sys

from studio.paths import default_detunify_studio_root, resolve_config_path

UNIFY_MOUNT_PREFIX = '/unify'

_unify_ready = False
_unify_root = ''


def resolve_detunify_studio_root(config=None):
    """DetUnify-Studio 仓库根目录（与 predict_runtime 一致）。"""
    if config is None:
        from server.core import load_config
        config = load_config()
    root = str(config.get('detunify_studio_root') or '').strip()
    if root:
        resolved = resolve_config_path(root, must_exist=True)
        if resolved:
            return resolved
    fallback = default_detunify_studio_root()
    return fallback if fallback and os.path.isdir(fallback) else ''


def is_unify_available(config=None):
    return bool(resolve_detunify_studio_root(config))


def _load_detunify_app():
    """惰性加载 DetUnify Flask app（避免与 DefectLoop 根 app.py 模块名冲突）。"""
    root = resolve_detunify_studio_root()
    if not root:
        raise RuntimeError('DetUnify-Studio 未配置或目录不存在')
    app_dir = os.path.join(root, 'app')
    app_py = os.path.join(app_dir, 'app.py')
    if not os.path.isfile(app_py):
        raise RuntimeError(f'DetUnify app 入口不存在: {app_py}')

    for path in (app_dir, root):
        if path not in sys.path:
            sys.path.insert(0, path)

    os.environ['DETUNIFY_MOUNT_PREFIX'] = UNIFY_MOUNT_PREFIX
    spec = importlib.util.spec_from_file_location('detunify_web_app', app_py)
    if spec is None or spec.loader is None:
        raise RuntimeError('无法加载 DetUnify app 模块')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    unify_app = getattr(module, 'app', None)
    if unify_app is None:
        raise RuntimeError('DetUnify app.py 未导出 app 对象')
    return unify_app


def register_unify_mount(app) -> bool:
    """将 DetUnify Web UI 挂到 /unify；成功返回 True。"""
    global _unify_ready, _unify_root
    if _unify_ready:
        return True
    root = resolve_detunify_studio_root()
    if not root:
        return False
    try:
        unify_app = _load_detunify_app()
    except Exception as exc:  # noqa: BLE001
        print(f'⚠️ DetUnify 挂载失败: {exc}')
        return False

    from werkzeug.middleware.dispatcher import DispatcherMiddleware

    _unify_root = root
    # 保留已有中间件链（若后续叠加其它 WSGI 中间件）
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {UNIFY_MOUNT_PREFIX: unify_app.wsgi_app})
    _unify_ready = True
    print(f'✓ DetUnify 已挂载于 {UNIFY_MOUNT_PREFIX}（{root}）')
    return True


def is_unify_mounted():
    return _unify_ready
