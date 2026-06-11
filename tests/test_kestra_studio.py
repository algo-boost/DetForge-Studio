"""Kestra Studio 嵌入配置 API。"""
from __future__ import annotations

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_kestra_studio_config(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    monkeypatch.setenv('KESTRA_URL', 'http://127.0.0.1:8080')
    r = app_client.get('/api/flows/kestra/studio')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['enabled'] is True
    assert data['embed_url'] == '/kestra-embed/ui/main/flows/iisp'
    assert data['proxy_enabled'] is True
    assert data['namespace'] == 'iisp'


def test_kestra_studio_custom_path(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    monkeypatch.setenv('KESTRA_URL', 'http://127.0.0.1:8080')
    r = app_client.get('/api/flows/kestra/studio?path=executions/iisp/foo/bar')
    assert r.status_code == 200
    assert r.get_json()['data']['embed_url'] == '/kestra-embed/executions/iisp/foo/bar'
