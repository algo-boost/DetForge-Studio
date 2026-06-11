"""Flask 应用上下文（CLI / Gateway 共用）。"""
from __future__ import annotations

from contextlib import contextmanager


@contextmanager
def app_context():
    from server.factory import create_app

    app = create_app()
    with app.app_context():
        yield app
