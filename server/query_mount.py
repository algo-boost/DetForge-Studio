"""Query 工具 UI 同进程挂载：/tools/query（委托 ui_server）。"""
from __future__ import annotations

from tools.query.ui_server import (
    DEFAULT_MOUNT_PREFIX,
    is_query_tool_ui_built,
    load_vite_manifest,
    register_query_ui_routes,
    resolve_query_tool_ui_root,
)

QUERY_MOUNT_PREFIX = DEFAULT_MOUNT_PREFIX

_query_ui_ready = False


def is_query_tool_ui_available(config=None) -> bool:
    return is_query_tool_ui_built(config)


def is_query_tool_ui_mounted() -> bool:
    return _query_ui_ready


def _load_vite_manifest(static_folder):
    return load_vite_manifest(static_folder)


def register_query_tool_mount(app) -> bool:
    global _query_ui_ready
    if _query_ui_ready:
        return True
    ok = register_query_ui_routes(app, mount_prefix=QUERY_MOUNT_PREFIX)
    if ok:
        _query_ui_ready = True
        root = resolve_query_tool_ui_root()
        print(f'✓ Query 工具 UI 已挂载于 {QUERY_MOUNT_PREFIX}（{root}）')
    return ok
