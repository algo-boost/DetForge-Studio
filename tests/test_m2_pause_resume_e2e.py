"""M2-run smoke-query 与 Pause/Resume 辅助测试。"""
from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_smoke_query_invoke_creates_task_dir(app_client, tmp_path, monkeypatch):
    monkeypatch.setitem(app_client.application.config, 'UPLOAD_FOLDER', str(tmp_path))
    r = app_client.post(
        '/v1/tools/smoke-query/invoke',
        data=json.dumps({
            'run_id': 'm2-smoke',
            'step_id': 'query',
            'params': {'row_count': 2},
            'inputs': {'upstream': {}},
        }),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body['status'] == 'done'
    assert body['outputs']['count'] == 2
    task_id = body['outputs']['task_id']
    task_dir = os.path.join(tmp_path, task_id)
    assert os.path.isdir(task_dir)
    assert os.path.isfile(os.path.join(task_dir, 'result.csv'))
    assert os.path.isfile(os.path.join(task_dir, '_annotations.coco.json'))


def test_summarize_paused_ui_url_uses_curation_id():
    from orchestration.kestra_client import summarize_paused

    summary = summarize_paused({
        'id': 'ex-1',
        'namespace': 'iisp',
        'flowId': 'daily_ng_curation_smoke',
        'state': {'startDate': '2026-06-09T00:00:00Z'},
        'taskRunList': [{
            'state': {'current': 'PAUSED'},
            'description': 'batch_id=77',
        }],
    })
    assert summary['ui_url'] == '/curation?id=77'
    assert summary['batch_id'] == '77'


def test_daily_ng_smoke_flow_yaml_exists():
    from orchestration.loader import discover_kestra_flows

    flows = discover_kestra_flows()
    assert any(f['id'] == 'daily_ng_curation_smoke' for f in flows)
