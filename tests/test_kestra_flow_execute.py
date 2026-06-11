"""Kestra Flow 触发与 inputs 解析测试。"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_parse_kestra_inputs_daily_ng():
    from orchestration.kestra_inputs import parse_kestra_inputs

    flow = {
        'inputs': [
            {'id': 'strategy_id', 'type': 'STRING', 'defaults': 'daily_trawl'},
            {'id': 'time_window', 'type': 'JSON', 'defaults': '{"preset":"yesterday"}'},
            {'id': 'reviewer', 'type': 'STRING', 'required': False},
        ],
    }
    schema = parse_kestra_inputs(flow)
    assert schema['strategy_id']['type'] == 'strategy'
    assert schema['strategy_id']['default'] == 'daily_trawl'
    assert schema['time_window']['type'] == 'time_window'
    assert schema['time_window']['default'] == {'preset': 'yesterday'}
    assert schema['reviewer']['required'] is False


def test_extract_kestra_task_outline():
    from orchestration.kestra_inputs import extract_kestra_task_outline

    flow = {
        'tasks': [
            {'id': 'query', 'type': 'io.kestra.plugin.core.http.Request'},
            {
                'id': 'after_query',
                'type': 'io.kestra.plugin.core.flow.If',
                'then': [
                    {'id': 'human_edit', 'type': 'io.kestra.plugin.core.flow.Pause'},
                ],
            },
        ],
    }
    outline = extract_kestra_task_outline(flow)
    ids = [n['id'] for n in outline]
    assert 'query' in ids
    assert 'human_edit' in ids


def test_flow_catalog_kestra_runnable_when_enabled(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    r = app_client.get('/api/flows/list')
    assert r.status_code == 200
    flows = r.get_json()['data']
    kestra = [f for f in flows if f.get('engine') == 'kestra']
    assert kestra
    daily = next(f for f in kestra if f['id'] == 'daily_ng_curation')
    assert daily['runnable'] is True
    assert daily['kestra_enabled'] is True
    assert daily['params_schema']['strategy_id']['type'] == 'strategy'
    assert len(daily['nodes']) >= 1


def test_flow_catalog_kestra_not_runnable_when_disabled(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '0')
    r = app_client.get('/api/flows/list')
    daily = next(f for f in r.get_json()['data'] if f['id'] == 'daily_ng_curation')
    assert daily['runnable'] is False
    assert daily['kestra_enabled'] is False


def test_kestra_execute_disabled(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '0')
    r = app_client.post(
        '/api/flows/kestra/execute',
        data=json.dumps({'flow_id': 'daily_ng_curation'}),
        content_type='application/json',
    )
    assert r.status_code == 503


@patch('orchestration.kestra_client.execute_flow')
def test_kestra_execute_ok(mock_exec, app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    mock_exec.return_value = {
        'execution_id': 'ex-test-1',
        'namespace': 'iisp',
        'flow_id': 'daily_ng_curation_smoke',
        'state': 'RUNNING',
        'kestra_url': 'http://127.0.0.1:8080/ui/main/executions/iisp/daily_ng_curation_smoke/ex-test-1',
    }
    r = app_client.post(
        '/api/flows/kestra/execute',
        data=json.dumps({
            'flow_id': 'daily_ng_curation_smoke',
            'inputs': {'strategy_id': 'daily_trawl'},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['data']['run_key'] == 'kestra:ex-test-1'
    assert body['data']['execution_id'] == 'ex-test-1'
    mock_exec.assert_called_once()
    call_kw = mock_exec.call_args
    assert call_kw[0][0] == 'daily_ng_curation_smoke'


def test_kestra_execute_unknown_flow(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    r = app_client.post(
        '/api/flows/kestra/execute',
        data=json.dumps({'flow_id': 'no_such_flow_xyz'}),
        content_type='application/json',
    )
    assert r.status_code == 404
