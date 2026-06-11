"""Gateway Contract v1 与工作台 API 测试。"""
from __future__ import annotations

import json

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_v1_list_tools(app_client):
    r = app_client.get('/v1/tools')
    assert r.status_code == 200
    data = r.get_json()
    assert 'tools' in data
    ids = {t['id'] for t in data['tools']}
    assert 'query' in ids


def test_v1_invoke_unknown_tool(app_client):
    r = app_client.post(
        '/v1/tools/no-such-tool/invoke',
        data=json.dumps({'params': {}, 'inputs': {}}),
        content_type='application/json',
    )
    assert r.status_code == 404
    body = r.get_json()
    assert body['status'] == 'failed'
    assert body['error']


def test_v1_invoke_contract_shape(app_client):
    r = app_client.post(
        '/v1/tools/gate-human/invoke',
        data=json.dumps({
            'run_id': 'test-run',
            'step_id': 'gate',
            'params': {'batch_id': 'b1'},
            'inputs': {'upstream': {}},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert set(body.keys()) == {'status', 'outputs', 'artifacts', 'error'}
    assert body['status'] in ('done', 'waiting_human', 'skipped', 'failed')


def test_workbench_todos(app_client):
    r = app_client.get('/api/workbench/todos')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert isinstance(data['data'], list)


def test_workbench_summary(app_client):
    r = app_client.get('/api/workbench/summary')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    summary = data['data']
    assert 'todo_count' in summary
    assert 'active_query_count' in summary


def test_discover_kestra_flows():
    from orchestration.loader import discover_kestra_flows
    flows = discover_kestra_flows()
    ids = {f['id'] for f in flows}
    assert 'daily_ng_curation' in ids
