"""query / query-strategy 工具包测试。"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _last_json_line(text: str) -> dict:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith('{'):
            return json.loads(line)
    raise AssertionError(f'no JSON in stdout: {text[:200]}')


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_query_manifest_valid():
    from capabilities.manifest import load_manifest, validate_manifest
    path = ROOT / 'tools/query/tool.manifest.json'
    data = load_manifest(str(path))
    assert not validate_manifest(data, path=str(path))
    assert data['entry']['cli']
    assert data['version'] == '1.2.0'


def test_query_strategy_manifest_valid():
    from capabilities.manifest import load_manifest, validate_manifest
    path = ROOT / 'tools/query_strategy/tool.manifest.json'
    data = load_manifest(str(path))
    assert not validate_manifest(data, path=str(path))


def test_query_dispatch_strategy_list():
    from tools.query.service import dispatch
    out = dispatch({'action': 'strategy.list'})
    assert out['action'] == 'strategy.list'
    assert out['count'] >= 1
    assert any(s.get('id') == 'daily_trawl' for s in out['strategies'])


def test_query_dispatch_legacy_strategy_list():
    from tools.query.service import dispatch
    out = dispatch({'action': 'list'})
    assert out['action'] == 'strategy.list'


def test_query_strategy_compat_service():
    from tools.query_strategy.service import run
    out = run({'action': 'get', 'strategy_id': 'daily_trawl'})
    assert out['strategy']['id'] == 'daily_trawl'
    assert out['strategy'].get('sql_template')


def test_query_registered_in_gateway(app_client):
    r = app_client.get('/v1/tools')
    ids = {t['id'] for t in r.get_json().get('tools', [])}
    assert 'query' in ids
    assert 'query-strategy' in ids


def test_query_strategy_invoke_gateway(app_client):
    r = app_client.post(
        '/v1/tools/query-strategy/invoke',
        data=json.dumps({
            'run_id': 'test',
            'step_id': 'main',
            'params': {'action': 'list'},
            'inputs': {},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'done'
    assert body['outputs']['count'] >= 1
    assert body['outputs']['action'] == 'strategy.list'


def test_query_invoke_strategy_list(app_client):
    r = app_client.post(
        '/v1/tools/query/invoke',
        data=json.dumps({
            'run_id': 'test',
            'params': {'action': 'strategy.list'},
            'inputs': {},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    assert r.get_json()['outputs']['action'] == 'strategy.list'


def test_query_cli_list_subprocess():
    proc = subprocess.run(
        [sys.executable, '-m', 'tools.query.cli', 'strategy', 'list'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0
    body = _last_json_line(proc.stdout)
    assert body['status'] == 'done'


@patch('tools.query.capability.dispatch')
def test_query_capability_skipped(mock_dispatch, app_client):
    mock_dispatch.return_value = {'skipped': True, 'reason': 'empty_result', 'count': 0}
    r = app_client.post(
        '/v1/tools/query/invoke',
        data=json.dumps({
            'run_id': 'test',
            'params': {'strategy_id': 'daily_trawl'},
            'inputs': {},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    assert r.get_json()['status'] == 'skipped'


def test_iisp_tool_invoke_query_strategy():
    proc = subprocess.run(
        [sys.executable, '-m', 'cli.main', 'tool', 'invoke', 'query-strategy',
         '--param', 'action=list'],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    assert proc.returncode == 0
    body = _last_json_line(proc.stdout)
    assert body['status'] == 'done'
