"""query REST 薄代理测试。"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_query_tool_status(app_client):
    r = app_client.get('/api/query-tool/status')
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['tool_id'] == 'query'
    assert '/query' in body['routes']


def test_query_tool_invoke_strategy_list(app_client):
    r = app_client.post(
        '/api/query-tool/invoke',
        data=json.dumps({'params': {'action': 'strategy.list'}}),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert body['outputs']['action'] == 'strategy.list'


def test_rest_proxy_list_strategies(app_client):
    r = app_client.get('/api/strategies')
    assert r.status_code == 200
    body = r.get_json()
    assert body['success'] is True
    assert isinstance(body['data'], list)
    assert body['data']


def test_rest_proxy_get_daily_trawl(app_client):
    r = app_client.get('/api/strategies/daily_trawl')
    assert r.status_code == 200
    assert r.get_json()['data']['id'] == 'daily_trawl'


def test_rest_proxy_get_strategy_variables(app_client):
    r = app_client.get('/api/strategies/daily_trawl/variables')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert 'custom_vars' in data or 'system_vars' in data


@patch('tools.query.service.sync.run_sync')
def test_rest_proxy_post_query(mock_run, app_client):
    mock_run.return_value = {'action': 'run', 'success': True, 'count': 0, 'task_id': 't1'}
    r = app_client.post(
        '/api/query',
        data=json.dumps({'sql': 'SELECT 1', 'strategy_id': 'daily_trawl'}),
        content_type='application/json',
    )
    assert r.status_code == 200
    assert r.get_json()['success'] is True
    mock_run.assert_called_once()


def test_dispatch_strategy_execute_action():
    from tools.query.service.dispatch import resolve_action
    assert resolve_action({'action': 'strategy.execute'}) == 'strategy.execute'
    assert resolve_action({'action': 'run'}) == 'run'
