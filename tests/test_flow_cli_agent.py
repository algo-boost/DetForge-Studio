"""flow pipeline validate / MCP API。"""
from __future__ import annotations

import pytest


def test_validate_legacy_welcome_demo():
    from orchestration.loader import load_pipeline_yaml
    from orchestration.pipeline_validate import validate_pipeline_any

    path = 'iisp-catalog/pipelines/demo/welcome_flow.yaml'
    defn = load_pipeline_yaml(path)
    errors = validate_pipeline_any(defn, path=path)
    assert errors == []


def test_validate_rejects_kestra_tasks_format():
    from orchestration.pipeline_validate import validate_pipeline_any

    defn = {
        'id': 'bad',
        'tasks': [{'id': 'x', 'type': 'io.kestra.plugin.core.http.Request'}],
    }
    errors = validate_pipeline_any(defn)
    assert any('Kestra' in e for e in errors)


def test_list_tools_for_agent():
    from orchestration.agent_mcp_api import list_tools_for_agent

    data = list_tools_for_agent()
    assert 'tools' in data
    assert len(data['tools']) >= 5


def test_validate_pipeline_text_inline():
    from orchestration.agent_mcp_api import validate_pipeline_for_agent

    yaml_text = 'id: t\nnodes:\n  - id: a\n    tool: smoke-query\n'
    out = validate_pipeline_for_agent(yaml_text=yaml_text)
    assert out['valid'] is True
    assert out['engine'] == 'legacy'


def test_invoke_blocked_by_default(monkeypatch):
    from orchestration.agent_mcp_api import invoke_tool_for_agent

    monkeypatch.delenv('IISP_AGENT_ALLOW_INVOKE', raising=False)
    with pytest.raises(PermissionError):
        invoke_tool_for_agent('smoke-query', params={'row_count': 1})
