"""Agent 自举上下文。"""
from orchestration.agent_context import build_agent_context, discover_skills


def test_build_agent_context_includes_skills():
    ctx = build_agent_context()
    assert ctx['version'] == '1.0'
    assert ctx['entrypoints']['agents_md'] == 'AGENTS.md'
    skills = ctx['skills']
    assert len(skills) >= 10
    ids = {s['id'] for s in skills}
    assert 'iisp-compose-flow' in ids
    assert 'iisp-vibe-guardrails' in ids


def test_discover_skills_paths_under_agent():
    for row in discover_skills():
        assert row['path'].startswith('agent/skills/')
        assert row['path'].endswith('SKILL.md')
