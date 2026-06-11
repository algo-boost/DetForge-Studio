"""工具集成 config 与 API 测试。"""
from __future__ import annotations

import pytest


def test_get_integration_mode_defaults_embedded():
    from server.tool_integration import get_integration_mode
    assert get_integration_mode('query', config={}) == 'embedded'
    assert get_integration_mode('viz', config={}) == 'embedded'


def test_get_integration_mode_from_config():
    from server.tool_integration import get_integration_mode, get_remote_url
    cfg = {'query_tool': {'integration': 'remote', 'remote_url': 'http://localhost:6021/'}}
    assert get_integration_mode('query', config=cfg) == 'remote'
    assert get_remote_url('query', config=cfg) == 'http://localhost:6021'


def test_build_integration_payload():
    from server.tool_integration import build_integration_payload
    out = build_integration_payload('viz', config={}, extra={'available': True})
    assert out['tool_id'] == 'viz'
    assert out['integration'] == 'embedded'
    assert out['mount_prefix'] == '/viz'
    assert out['hash_routing'] is False
    assert out['available'] is True


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_generic_integration_api_query(app_client):
    r = app_client.get('/api/tools/query/integration')
    assert r.status_code == 200
    body = r.get_json()
    assert body['tool_id'] == 'query'
    assert body['integration'] == 'embedded'
    assert body['mount_prefix'] == '/tools/query'
    assert body['hash_routing'] is True


def test_generic_integration_api_viz(app_client):
    r = app_client.get('/api/tools/viz/integration')
    assert r.status_code == 200
    body = r.get_json()
    assert body['mount_prefix'] == '/viz'
    assert 'available' in body


def test_legacy_query_status_still_works(app_client):
    r = app_client.get('/api/query-tool/status')
    assert r.status_code == 200
    assert r.get_json()['integration'] == 'embedded'
