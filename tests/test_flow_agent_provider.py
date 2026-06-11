"""Flow agent provider 单元测试。"""
from __future__ import annotations

import os

from orchestration import flow_agent_service as fas


def test_agent_provider_claude_aliases():
    old = os.environ.get('IISP_FLOW_AGENT_PROVIDER')
    try:
        os.environ['IISP_FLOW_AGENT_PROVIDER'] = 'claude_code'
        assert fas._agent_provider() == 'claude_code'
        os.environ['IISP_FLOW_AGENT_PROVIDER'] = 'claude-code'
        assert fas._agent_provider() == 'claude_code'
    finally:
        if old is None:
            os.environ.pop('IISP_FLOW_AGENT_PROVIDER', None)
        else:
            os.environ['IISP_FLOW_AGENT_PROVIDER'] = old


def test_claude_code_chat_invokes_subprocess(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        class R:
            returncode = 0
            stdout = '```yaml\nid: demo\nnamespace: iisp\ntasks: []\n```'
            stderr = ''
        return R()

    monkeypatch.setenv('IISP_FLOW_AGENT_PROVIDER', 'claude_code')
    monkeypatch.setattr(fas, '_resolve_claude_cmd', lambda: ['node', '/tmp/claude-code/cli.js'])
    monkeypatch.setattr(fas.subprocess, 'run', fake_run)

    out = fas._claude_code_chat('system', '写一个 smoke flow')
    assert out.text and 'id: demo' in out.text
    assert calls[0][:2] == ['node', '/tmp/claude-code/cli.js']
    assert calls[0][2] == '-p'
    assert 'USER: 写一个 smoke flow' in calls[0][3]


def test_stream_compose_yields_final(monkeypatch):
    from orchestration.flow_agent_service import LlmResult

    monkeypatch.setenv('IISP_FLOW_AGENT_PROVIDER', 'openai')
    monkeypatch.setattr(
        'orchestration.flow_agent_service._llm_chat',
        lambda *a, **k: LlmResult('```yaml\nid: demo\nnamespace: iisp\ntasks: []\n```', None),
    )
    events = list(fas.stream_compose('做个 demo flow'))
    types = [e.get('type') for e in events]
    assert 'start' in types
    assert 'delta' in types
    assert types[-1] == 'final'
    final = events[-1]['data']
    assert final['success'] is True
    assert 'id: demo' in (final.get('yaml') or '')


def test_resolve_claude_cmd_finds_npm_global(monkeypatch):
    cli = '/opt/homebrew/lib/node_modules/@anthropic-ai/claude-code/cli.js'
    monkeypatch.delenv('IISP_FLOW_AGENT_CLAUDE_BIN', raising=False)
    monkeypatch.setattr(fas.shutil, 'which', lambda name: 'node' if name == 'node' else None)
    monkeypatch.setattr(fas, '_npm_claude_cli_paths', lambda: [cli] if os.path.isfile(cli) else [])
    cmd = fas._resolve_claude_cmd()
    if os.path.isfile(cli):
        assert cmd == ['node', cli]
