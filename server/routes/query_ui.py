"""注册 Query UI 挂载（/tools/query）。"""
from __future__ import annotations

from server.query_mount import is_query_tool_ui_available, register_query_tool_mount

_query_mounted = False


def ensure_query_tool_mounted(app) -> bool:
    global _query_mounted
    if _query_mounted:
        return True
    if not is_query_tool_ui_available():
        return False
    try:
        _query_mounted = register_query_tool_mount(app)
    except Exception as exc:  # noqa: BLE001
        print(f'⚠️ Query UI 挂载失败: {exc}')
        _query_mounted = False
    return _query_mounted
