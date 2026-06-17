"""Flask 应用上下文（CLI / Gateway 共用）。"""
from __future__ import annotations

from contextlib import contextmanager

_cached_app = None


@contextmanager
def app_context():
    """优先复用当前请求或 app 模块中的 Flask 实例，避免重复 create_app 触发副作用。"""
    from flask import has_app_context, current_app

    if has_app_context():
        yield current_app
        return

    global _cached_app
    if _cached_app is None:
        try:
            from app import app as main_app
            _cached_app = main_app
        except ImportError:
            from server.factory import create_app
            _cached_app = create_app()
    with _cached_app.app_context():
        yield _cached_app
