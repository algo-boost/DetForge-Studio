"""Kestra Flow 只读流程图解析测试。"""
from __future__ import annotations

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_parse_tool_id_from_uri():
    from orchestration.kestra_graph import parse_tool_id_from_uri

    assert parse_tool_id_from_uri('{{ envs.iisp_base }}/v1/tools/query/invoke') == 'query'
    assert parse_tool_id_from_uri('http://x/v1/tools/curation-create/invoke') == 'curation-create'
    assert parse_tool_id_from_uri('/other') is None


def test_extract_kestra_flow_graph_smoke():
    from orchestration.kestra_graph import extract_kestra_flow_graph

    flow = {
        'tasks': [
            {
                'id': 'query',
                'type': 'io.kestra.plugin.core.http.Request',
                'uri': '{{ envs.iisp_base }}/v1/tools/smoke-query/invoke',
                'body': '{"params":{}}',
            },
            {
                'id': 'after_query',
                'type': 'io.kestra.plugin.core.flow.If',
                'condition': '{{ true }}',
                'then': [
                    {'id': 'batch', 'type': 'io.kestra.plugin.core.http.Request',
                     'uri': '{{ envs.iisp_base }}/v1/tools/curation-create/invoke'},
                    {'id': 'human_edit', 'type': 'io.kestra.plugin.core.flow.Pause'},
                ],
            },
        ],
    }
    graph = extract_kestra_flow_graph(flow)
    ids = [n['id'] for n in graph['nodes']]
    assert 'query' in ids
    assert 'after_query' in ids
    assert 'batch' in ids
    assert 'human_edit' in ids
    query = next(n for n in graph['nodes'] if n['id'] == 'query')
    assert query['tool_id'] == 'smoke-query'
    assert query['request_body_preview']


def test_build_flow_graph_enriches_tool_manifest():
    from capabilities import init_registry
    from orchestration.kestra_graph import build_flow_graph

    init_registry()
    flow = {
        'id': 'test_flow',
        'tasks': [
            {
                'id': 'notify',
                'type': 'io.kestra.plugin.core.http.Request',
                'uri': '{{ envs.iisp_base }}/v1/tools/notify/invoke',
            },
        ],
    }
    graph = build_flow_graph(flow, engine='kestra')
    node = graph['nodes'][0]
    assert node['tool']['id'] == 'notify'
    assert 'outputs' in node['tool']


def test_merge_run_status_enriches_node():
    from capabilities import init_registry
    from orchestration.kestra_graph import build_flow_graph, merge_run_status

    init_registry()
    flow = {
        'id': 'test_flow',
        'tasks': [
            {
                'id': 'notify',
                'type': 'io.kestra.plugin.core.http.Request',
                'uri': '{{ envs.iisp_base }}/v1/tools/notify/invoke',
            },
        ],
    }
    graph = build_flow_graph(flow, engine='kestra')
    steps = [{
        'step_id': 'notify',
        'status': 'done',
        'started_at': '2026-06-11T00:00:00+00:00',
        'ended_at': '2026-06-11T00:00:03+00:00',
        'io': {
            'status': 'ok',
            'http_code': 200,
            'reason': '已发送',
            'outputs': {'sent': True},
            'artifacts': ['report.txt'],
            'raw_body': {'params': {}, 'outputs': {'sent': True}},
        },
    }]
    merged = merge_run_status(graph, steps)
    node = merged['nodes'][0]
    assert node['status'] == 'done'
    assert node['duration_seconds'] == 3.0
    rd = node['run_detail']
    assert rd['http_code'] == 200
    assert rd['tool_status'] == 'ok'
    assert rd['artifacts'] == ['report.txt']
    assert rd['raw'] is not None


def test_flow_graph_api(app_client):
    r = app_client.get('/api/flows/pipelines/closed_loop_demo_smoke/graph')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data['flow_id'] == 'closed_loop_demo_smoke'
    assert len(data['nodes']) >= 3
    query = next((n for n in data['nodes'] if n['id'] == 'query'), None)
    assert query is not None
    assert query.get('tool_id') == 'smoke-query'
