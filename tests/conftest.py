"""pytest 路径与 Flask test_client 夹具。"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 测试进程内不启动 worker，避免端口/子进程干扰
os.environ.setdefault('PC_NO_WORKER', '1')


@pytest.fixture(scope='session')
def app():
    from server.factory import create_app
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def json_headers():
    return {'Content-Type': 'application/json'}
