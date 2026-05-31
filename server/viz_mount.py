"""COCOVisualizer 同进程挂载：/viz 前缀 API + 静态 + UI。"""
from __future__ import annotations

import json
import os
import sys

from flask import send_from_directory, abort

from studio.paths import PROJECT_ROOT

VIZ_MOUNT_PREFIX = '/viz'

_viz_ready = False
_coco_root = ''


def resolve_coco_visualizer_root(config=None):
    """COCOVisualizer 仓库根目录（默认同 monorepo sibling）。"""
    if config is None:
        from server.core import load_config
        config = load_config()
    root = str(config.get('coco_visualizer_root') or '').strip()
    if not root:
        sibling = os.path.normpath(os.path.join(PROJECT_ROOT, '..', 'COCOVisualizer'))
        if os.path.isdir(sibling):
            root = sibling
    return os.path.normpath(root) if root and os.path.isdir(root) else ''


def is_viz_available(config=None):
    return bool(resolve_coco_visualizer_root(config))


def _load_vite_manifest(static_folder):
    dist_dir = os.path.join(static_folder, 'dist')
    for name in ('manifest.json', os.path.join('.vite', 'manifest.json')):
        path = os.path.join(dist_dir, name)
        if os.path.isfile(path):
            try:
                manifest = json.loads(open(path, encoding='utf-8').read())
            except Exception:
                continue
            entry_key = next(
                (k for k, v in manifest.items() if isinstance(v, dict) and v.get('isEntry')),
                None,
            )
            if not entry_key:
                continue
            entry_meta = manifest[entry_key]

            def collect_css(key, seen):
                meta = manifest.get(key) or {}
                out = []
                for css in meta.get('css') or []:
                    if css not in seen:
                        seen.add(css)
                        out.append(css)
                for imp in meta.get('imports') or []:
                    out.extend(collect_css(imp, seen))
                return out

            seen = set()
            css_files = collect_css(entry_key, seen)
            return {'entry': entry_meta.get('file', entry_key), 'css': css_files}
    return None


def register_viz_mount(app) -> bool:
    """将 COCOVisualizer 挂到 /viz；成功返回 True。"""
    global _viz_ready, _coco_root
    root = resolve_coco_visualizer_root()
    if not root:
        return False
    if root not in sys.path:
        sys.path.insert(0, root)

    from backend.blueprints import register_blueprints as register_coco_blueprints
    from backend import config as coco_config

    _coco_root = root
    register_coco_blueprints(app, url_prefix=VIZ_MOUNT_PREFIX)

    template_folder = str(coco_config.TEMPLATE_FOLDER)
    static_folder = str(coco_config.STATIC_FOLDER)

    @app.route(f'{VIZ_MOUNT_PREFIX}/')
    @app.route(VIZ_MOUNT_PREFIX)
    def viz_index():
        from jinja2 import Environment, FileSystemLoader, select_autoescape
        vite_assets = _load_vite_manifest(static_folder)
        env = Environment(
            loader=FileSystemLoader(template_folder),
            autoescape=select_autoescape(['html', 'xml']),
        )
        tpl = env.get_template('index.html')
        return tpl.render(vite_assets=vite_assets, mount_prefix=VIZ_MOUNT_PREFIX)

    @app.route(f'{VIZ_MOUNT_PREFIX}/static/dist/<path:filename>')
    def viz_static_dist(filename):
        return send_from_directory(os.path.join(static_folder, 'dist'), filename)

    @app.route(f'{VIZ_MOUNT_PREFIX}/static/<path:filename>')
    def viz_static(filename):
        return send_from_directory(static_folder, filename)

    # img / a 标签不走 fetch 拦截，需在根路径代理 COCO 图片 API
    @app.route('/api/get_image', methods=['GET'])
    def root_proxy_coco_get_image():
        from backend.blueprints.images_bp import get_image as coco_get_image
        return coco_get_image()

    _viz_ready = True
    return True


def get_coco_dataset_service():
    """惰性导入 COCO dataset_service（需已配置 coco_visualizer_root）。"""
    root = resolve_coco_visualizer_root()
    if not root:
        raise RuntimeError('COCOVisualizer 未配置或目录不存在')
    if root not in sys.path:
        sys.path.insert(0, root)
    from backend.services import dataset_service
    return dataset_service
