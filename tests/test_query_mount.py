"""Query UI /tools/query 挂载测试。"""
from __future__ import annotations

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_query_tool_mount_index(app_client):
    r = app_client.get('/tools/query/')
    assert r.status_code == 200
    assert b'id="root"' in r.data


def test_query_tool_status_mount_fields(app_client):
    r = app_client.get('/api/query-tool/status')
    assert r.status_code == 200
    body = r.get_json()
    assert body['mount_prefix'] == '/tools/query'
    assert 'mount_available' in body
    assert body['mount_available'] is True
