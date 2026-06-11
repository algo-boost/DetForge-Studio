"""U3 Flow Catalog / Runs API 测试。"""
from __future__ import annotations

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_flows_list(app_client):
    r = app_client.get('/api/flows/list')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    ids = {row['id'] for row in data['data']}
    assert 'welcome_demo' in ids or 'daily_ng_curation' in ids


def test_flows_releases(app_client):
    r = app_client.get('/api/flows/releases')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)


def test_flows_runs_list(app_client):
    r = app_client.get('/api/flows/runs')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)


def test_flow_run_welcome_demo(app_client):
    r = app_client.post(
        '/api/flows/run',
        json={'flow_id': 'welcome_demo', 'params': {'reviewer': 'test'}, 'auto_resume': True},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body.get('status') == 'done'
    run_id = body['data']['run_id']

    detail = app_client.get(f'/api/flows/runs/demo:{run_id}')
    assert detail.status_code == 404  # completed demo runs are not kept in memory


def test_flows_pipeline_yaml(app_client):
    r = app_client.get('/api/flows/pipelines/welcome_demo/yaml')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert 'welcome_demo' in data['data']['yaml']
