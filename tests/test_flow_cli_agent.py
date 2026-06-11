"""flow execute / export-shell / pipeline validate / MCP API。"""
from __future__ import annotations

import json
from unittest.mock import patch

import pytest


def test_validate_kestra_flow_smoke():
    from orchestration.loader import load_pipeline_yaml
    from orchestration.pipeline_validate import validate_pipeline_any

    path = 'iisp-catalog/pipelines/kestra/closed_loop_demo_smoke.yaml'
    defn = load_pipeline_yaml(path)
    errors = validate_pipeline_any(defn, path=path)
    assert errors == []


def test_validate_kestra_unknown_tool():
    from orchestration.pipeline_validate import validate_kestra_flow

    defn = {
        'id': 'bad',
        'tasks': [
            {
                'id': 'x',
                'type': 'io.kestra.plugin.core.http.Request',
                'uri': '{{ envs.iisp_base }}/v1/tools/no_such_tool_xyz/invoke',
            },
        ],
    }
    errors = validate_kestra_flow(defn)
    assert any('no_such_tool_xyz' in e for e in errors)


def test_export_shell_contains_invoke():
    from orchestration.flow_shell_export import export_kestra_flow_shell

    script = export_kestra_flow_shell('closed_loop_demo_smoke')
    assert 'tool invoke smoke-query' in script
    assert 'tool invoke curation-create' in script
    assert 'RUN_ID=' in script
    assert 'reviewer=' in script


@patch('orchestration.kestra_client.execute_flow')
def test_flow_execute_cli(mock_exec, monkeypatch):
    monkeypatch.setenv('KESTRA_ENABLED', '1')
    mock_exec.return_value = {
        'execution_id': 'ex-cli-1',
        'namespace': 'iisp',
        'flow_id': 'closed_loop_demo_smoke',
        'state': 'RUNNING',
        'kestra_url': 'http://127.0.0.1:8080/ui/main/executions/iisp/closed_loop_demo_smoke/ex-cli-1',
    }
    from cli.main import main

    rc = main(['flow', 'execute', 'closed_loop_demo_smoke', '--param', 'reviewer=demo'])
    assert rc == 0
    mock_exec.assert_called_once()


def test_list_tools_for_agent():
    from orchestration.agent_mcp_api import list_tools_for_agent

    data = list_tools_for_agent()
    assert 'tools' in data
    assert len(data['tools']) >= 5
    ids = {t['id'] for t in data['tools']}
    assert 'smoke-query' in ids or 'query' in ids


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
