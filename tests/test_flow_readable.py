"""Flow 可读化：YAML 注释 → 表单字段。"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SMOKE_YAML = ROOT / 'iisp-catalog' / 'pipelines' / 'kestra' / 'closed_loop_demo_smoke.yaml'


def test_parse_yaml_step_comments_smoke():
    from orchestration.flow_readable import parse_yaml_step_comments

    text = SMOKE_YAML.read_text(encoding='utf-8')
    meta = parse_yaml_step_comments(text)
    assert 'query' in meta
    assert 'batch' in meta
    assert '造样本查询任务' in meta['query'].get('title', '')
    assert 'row_count' in meta['query'].get('inputs_line', '')
    assert 'task_id' in meta['query'].get('outputs_line', '')


def test_build_node_readable_query():
    from orchestration.flow_readable import build_node_readable, parse_yaml_step_comments

    text = SMOKE_YAML.read_text(encoding='utf-8')
    meta = parse_yaml_step_comments(text)['query']
    node = {
        'id': 'query',
        'tool_id': 'smoke-query',
        'request_body_preview': '''
        "params": {
          "row_count": inputs.row_count,
          "strategy_id": "closed_loop_demo_smoke"
        }
        ''',
        'tool': {
            'label': '冒烟查询',
            'outputs': ['task_id', 'row_count'],
        },
    }
    readable = build_node_readable(node, yaml_meta=meta, flow_inputs={'row_count', 'reviewer'})
    keys = [f['key'] for f in readable['inputs']]
    assert 'row_count' in keys
    assert 'strategy_id' in keys
    row = next(f for f in readable['inputs'] if f['key'] == 'row_count')
    assert 'Flow 入参' in row['value']
    assert readable['outputs']
    assert any(o['key'] == 'task_id' for o in readable['outputs'])


def test_branch_readable_after_query():
    from orchestration.flow_readable import build_node_readable, parse_yaml_step_comments

    text = SMOKE_YAML.read_text(encoding='utf-8')
    # closed_loop_demo has branch; use its yaml
    demo_path = ROOT / 'iisp-catalog' / 'pipelines' / 'kestra' / 'closed_loop_demo.yaml'
    meta = parse_yaml_step_comments(demo_path.read_text(encoding='utf-8')).get('after_query', {})
    node = {
        'id': 'after_query',
        'tool_id': 'branch',
        'node_kind': 'branch',
        'description': '{{ fromJson(outputs.query.body).status == \'done\' }}',
    }
    readable = build_node_readable(node, yaml_meta=meta)
    assert readable['inputs']
    assert readable['outputs']
    assert 'query' in readable['branch_condition_human']


def test_flow_graph_api_has_readable(app_client):
    r = app_client.get('/api/flows/pipelines/closed_loop_demo_smoke/graph')
    assert r.status_code == 200
    data = r.get_json()['data']
    assert data.get('readable', {}).get('summary')
    query = next(n for n in data['nodes'] if n['id'] == 'query')
    readable = query.get('readable') or {}
    assert readable.get('inputs')
    assert readable['inputs'][0].get('title')
    assert readable['inputs'][0].get('description')


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
