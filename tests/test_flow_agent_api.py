"""Flow 编排助手 API 测试。"""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def app_client():
    from server.factory import create_app
    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_flow_agent_context(app_client):
    r = app_client.get('/api/flows/agent/context')
    assert r.status_code == 200
    data = r.get_json()
    assert data['success'] is True
    assert 'system_prompt' in data['data']
    assert 'llm_configured' in data['data']


def test_flow_agent_validate_welcome_yaml(app_client):
    r = app_client.get('/api/flows/pipelines/welcome_demo/yaml')
    assert r.status_code == 200
    yaml_text = r.get_json()['data']['yaml']
    vr = app_client.post('/api/flows/agent/validate', json={'yaml': yaml_text})
    assert vr.status_code == 200
    body = vr.get_json()
    assert body['success'] is True
    assert body['data']['valid'] is True
    assert body['data']['engine'] == 'legacy'


def test_flow_agent_preview_graph(app_client):
    r = app_client.get('/api/flows/pipelines/welcome_demo/yaml')
    yaml_text = r.get_json()['data']['yaml']
    pr = app_client.post('/api/flows/agent/preview-graph', json={'yaml': yaml_text})
    assert pr.status_code == 200
    body = pr.get_json()
    assert body['success'] is True
    assert body['data']['graph']['nodes']


def test_flow_agent_save_rejects_invalid(app_client):
    r = app_client.post('/api/flows/agent/save', json={'yaml': 'id: x\n'})
    assert r.status_code == 400
    body = r.get_json()
    assert body['success'] is False


def test_flow_agent_save_and_overwrite(app_client, tmp_path, monkeypatch):
    from orchestration import flow_agent_service as fas

    monkeypatch.setattr(fas, 'APP_ROOT', str(tmp_path))
    src = app_client.get('/api/flows/pipelines/welcome_demo/yaml').get_json()['data']['yaml']
    result = fas.save_flow_yaml(src)
    assert result['success'] is True
    fid = result['flow_id']
    saved = os.path.join(str(tmp_path), 'iisp-catalog', 'pipelines', 'legacy', f'{fid}.yaml')
    assert os.path.isfile(saved)
    again = fas.save_flow_yaml(src)
    assert again['success'] is False and again.get('exists') is True
    ow = fas.save_flow_yaml(src, overwrite=True)
    assert ow['success'] is True and ow['overwritten'] is True
