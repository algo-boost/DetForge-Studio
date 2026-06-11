"""Query UI 静态资源挂载 — IISP /tools/query 与独立部署共用。"""
from __future__ import annotations

import json
import os

from flask import send_from_directory

from studio.paths import default_query_tool_ui_root, resolve_config_path

DEFAULT_MOUNT_PREFIX = '/tools/query'


def resolve_query_tool_ui_root(config=None):
    if config is None:
        from server.core import load_config
        config = load_config()
    root = str(config.get('query_tool_ui_root') or '').strip()
    if root:
        resolved = resolve_config_path(root, must_exist=True)
        if resolved:
            return resolved
    fallback = default_query_tool_ui_root()
    return fallback if fallback and os.path.isdir(fallback) else ''


def load_vite_manifest(static_folder: str):
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


def is_query_tool_ui_built(config=None) -> bool:
    root = resolve_query_tool_ui_root(config)
    if not root:
        return False
    return load_vite_manifest(os.path.join(root, 'static')) is not None


def register_query_ui_routes(app, *, mount_prefix: str = DEFAULT_MOUNT_PREFIX) -> bool:
    """注册 Query SPA；mount_prefix='' 时独立部署根路径。"""
    root = resolve_query_tool_ui_root()
    if not root:
        return False
    template_folder = os.path.join(root, 'templates')
    static_folder = os.path.join(root, 'static')
    if not os.path.isfile(os.path.join(template_folder, 'index.html')):
        return False

    prefix = mount_prefix.rstrip('/') if mount_prefix else ''
    dist_base = f'{prefix}/static/dist' if prefix else '/static/dist'
    static_base = f'{prefix}/static' if prefix else '/static'

    def _render_index():
        from jinja2 import Environment, FileSystemLoader, select_autoescape

        vite_assets = load_vite_manifest(static_folder)
        env = Environment(
            loader=FileSystemLoader(template_folder),
            autoescape=select_autoescape(['html', 'xml']),
        )
        tpl = env.get_template('index.html')
        return tpl.render(vite_assets=vite_assets, mount_prefix=prefix)

    if prefix:
        app.add_url_rule(f'{prefix}/', endpoint='query_tool_index_slash', view_func=_render_index)
        app.add_url_rule(prefix, endpoint='query_tool_index', view_func=_render_index, strict_slashes=False)
    else:
        app.add_url_rule('/', endpoint='query_tool_index', view_func=_render_index, strict_slashes=False)

    @app.route(f'{dist_base}/<path:filename>', endpoint='query_tool_static_dist')
    def query_tool_static_dist(filename):
        return send_from_directory(os.path.join(static_folder, 'dist'), filename)

    @app.route(f'{static_base}/<path:filename>', endpoint='query_tool_static_assets')
    def query_tool_static_assets(filename):
        return send_from_directory(static_folder, filename)

    return True
