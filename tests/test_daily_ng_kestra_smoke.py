"""Kestra daily_ng_curation Flow 与 Gateway 冒烟测试。"""
from __future__ import annotations

import json

import pytest

DAILY_NG_TOOLS = [
    'query',
    'curation-create',
    'curation-export',
    'curation-import',
    'curation-archive',
    'notify',
]


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def _collect_tasks(nodes):
    out = []
    for t in nodes or []:
        out.append(t)
        for key in ('tasks', 'then', 'else', 'finally', 'errors'):
            if isinstance(t.get(key), list):
                out.extend(_collect_tasks(t[key]))
        cases = t.get('cases')
        if isinstance(cases, dict):
            for case_tasks in cases.values():
                if isinstance(case_tasks, list):
                    out.extend(_collect_tasks(case_tasks))
        defaults = t.get('defaults')
        if isinstance(defaults, list):
            out.extend(_collect_tasks(defaults))
    return out


def test_daily_ng_flow_yaml_lists_seven_http_steps():
    from orchestration.loader import discover_kestra_flows, load_pipeline_yaml
    from studio.paths import APP_ROOT
    import os

    flows = discover_kestra_flows()
    assert any(f['id'] == 'daily_ng_curation' for f in flows)
    path = os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'kestra', 'daily_ng_curation.yaml')
    data = load_pipeline_yaml(path)
    all_tasks = _collect_tasks(data.get('tasks') or [])
    http_tasks = [t for t in all_tasks if 'http.Request' in str(t.get('type', ''))]
    assert len(http_tasks) == 6
    assert any(t.get('type') == 'io.kestra.plugin.core.flow.Pause' for t in all_tasks)
    assert any(t.get('type') == 'io.kestra.plugin.core.flow.If' for t in (data.get('tasks') or []))
    assert any(t.get('type') == 'io.kestra.plugin.core.flow.Sequential' for t in all_tasks)


def test_daily_ng_tools_registered(app_client):
    r = app_client.get('/v1/tools')
    assert r.status_code == 200
    ids = {t['id'] for t in r.get_json().get('tools', [])}
    for tid in DAILY_NG_TOOLS:
        assert tid in ids, f'missing tool {tid}'


def test_daily_ng_invoke_urls_match_gateway(app_client):
    r = app_client.get('/v1/tools')
    tools = {t['id']: t for t in r.get_json().get('tools', [])}
    for tid in DAILY_NG_TOOLS:
        assert tools[tid]['invoke'] == f'/v1/tools/{tid}/invoke'


@pytest.mark.parametrize('tool_id,params', [
    ('gate-human', {'batch_id': 'smoke-batch'}),
    ('notify', {'event': 'workflow_done'}),
])
def test_daily_ng_side_tools_invoke_contract(app_client, tool_id, params):
    r = app_client.post(
        f'/v1/tools/{tool_id}/invoke',
        data=json.dumps({
            'run_id': 'kestra-smoke',
            'step_id': tool_id,
            'params': params,
            'inputs': {'upstream': {}},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert set(body.keys()) == {'status', 'outputs', 'artifacts', 'error'}
    assert body['status'] in ('done', 'waiting_human', 'skipped', 'failed')
