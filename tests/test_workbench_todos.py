"""工作台待办聚合（manual_qc / curation / workflow）。"""
from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@patch('server.services.workbench.collect_curation_pending')
@patch('server.services.workbench.collect_manual_qc_pending')
@patch('server.services.workbench.collect_kestra_paused')
@patch('server.services.workbench.collect_demo_flow_runs')
@patch('server.services.workbench.collect_workflow_runs')
def test_workbench_todos_aggregate_sources(
    mock_workflow,
    mock_demo,
    mock_kestra,
    mock_mqc,
    mock_curation,
    app_client,
):
    mock_workflow.return_value = [{
        'id': 9,
        'template_id': 'daily_ng',
        'created_at': '2026-06-09T10:00:00',
    }]
    mock_demo.return_value = []
    mock_kestra.return_value = []
    mock_mqc.return_value = [{
        'batch_id': '2026-06-09',
        'batch_key': '2026-06-09',
        'intake_count': 2,
        'confirmed_count': 1,
        'total': 3,
        'first_at': '2026-06-09T08:00:00',
    }]
    mock_curation.return_value = [{
        'id': 42,
        'batch_code': 'cur-42',
        'status': 'exported',
        'strategy_name': '日常捞图',
        'created_at': '2026-06-09T07:00:00',
        'pending_count': 5,
    }]

    r = app_client.get('/api/workbench/todos')
    assert r.status_code == 200
    todos = r.get_json()['data']
    kinds = {t['kind'] for t in todos}
    assert 'workflow_human_gate' in kinds
    assert 'manual_qc' in kinds
    assert 'curation_batch' in kinds

    mqc = next(t for t in todos if t['kind'] == 'manual_qc')
    assert mqc['href'] == '/manual-qc'
    assert '待核对 2' in mqc['subtitle']

    cur = next(t for t in todos if t['kind'] == 'curation_batch')
    assert cur['href'] == '/curation?id=42'
    assert '待回传 COCO' in cur['title']


@patch('server.services.workbench.collect_curation_pending')
@patch('server.services.workbench.collect_manual_qc_pending')
@patch('server.services.workbench.collect_kestra_paused')
@patch('server.services.workbench.collect_demo_flow_runs')
@patch('server.services.workbench.collect_workflow_runs')
def test_workbench_summary_includes_mqc_and_curation(
    mock_workflow,
    mock_demo,
    mock_kestra,
    mock_mqc,
    mock_curation,
    app_client,
):
    def workflow_side_effect(**kw):
        if kw.get('status') == 'running':
            return [{'id': 1}]
        return []

    mock_workflow.side_effect = workflow_side_effect
    mock_demo.return_value = []
    mock_kestra.return_value = []
    mock_mqc.return_value = [{'batch_id': 'b1', 'total': 1}]
    mock_curation.return_value = [{'id': 1, 'status': 'created'}]

    r = app_client.get('/api/workbench/summary')
    assert r.status_code == 200
    summary = r.get_json()['data']
    assert summary['todo_count'] == 2
    assert summary['manual_qc_batch_count'] == 1
    assert summary['curation_batch_count'] == 1
    assert summary['running_flow_count'] == 1
