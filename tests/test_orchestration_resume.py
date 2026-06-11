"""Resume API 与 Kestra 客户端测试。"""
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


def test_orchestration_list_paused_disabled(app_client, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '0')
    r = app_client.get('/v1/orchestration/executions/paused')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert data['data'] == []
    assert data['kestra_enabled'] is False


def test_orchestration_resume_requires_execution_id(app_client):
    r = app_client.post(
        '/v1/orchestration/resume',
        data=json.dumps({}),
        content_type='application/json',
    )
    assert r.status_code == 400
    assert r.get_json()['success'] is False


@patch('orchestration.kestra_client.resume_execution')
def test_orchestration_resume_ok(mock_resume, app_client):
    mock_resume.return_value = {'execution_id': 'ex-1', 'state': 'RUNNING'}
    r = app_client.post(
        '/v1/orchestration/resume',
        data=json.dumps({'execution_id': 'ex-1'}),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['data']['execution_id'] == 'ex-1'
    mock_resume.assert_called_once_with('ex-1', inputs=None)


def test_extract_batch_id_from_pause_description():
    from orchestration.kestra_client import extract_batch_id

    execution = {
        'taskRunList': [{
            'state': {'current': 'PAUSED'},
            'description': '请在 IISP 编辑；batch_id=42',
        }],
    }
    assert extract_batch_id(execution) == '42'


@patch('orchestration.kestra_client.list_paused_executions')
def test_workbench_todos_include_kestra(mock_list, app_client):
    mock_list.return_value = [{
        'id': 'ex-k1',
        'namespace': 'iisp',
        'flowId': 'daily_ng_curation',
        'state': {'startDate': '2026-06-09T00:00:00Z'},
        'taskRunList': [{
            'state': {'current': 'PAUSED'},
            'description': 'batch_id=99',
        }],
    }]
    r = app_client.get('/api/workbench/todos')
    assert r.status_code == 200
    todos = r.get_json()['data']
    kinds = {t['kind'] for t in todos}
    assert 'kestra_pause' in kinds
