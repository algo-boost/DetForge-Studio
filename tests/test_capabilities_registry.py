"""Capability Registry 与 Manifest 测试。"""
from __future__ import annotations

import os

import pytest


def test_init_registry_lists_builtin_tools():
    from capabilities.registry import init_registry
    reg = init_registry()
    tools = reg.list_tools()
    ids = {t['id'] for t in tools}
    assert 'query' in ids
    assert 'curation-create' in ids or 'gate-human' in ids


def test_manifest_validate_root_query():
    from capabilities.manifest import load_manifest, validate_manifest
    from studio.paths import APP_ROOT
    path = os.path.join(APP_ROOT, 'tool.manifest.json')
    if not os.path.isfile(path):
        pytest.skip('tool.manifest.json missing')
    data = load_manifest(path)
    errs = validate_manifest(data, path=path)
    assert errs == []


def test_step_bridge_registry_mode():
    os.environ['IISP_USE_REGISTRY'] = '1'
    from capabilities.step_bridge import use_registry
    assert use_registry() is True


def test_skill_parser_yf_demo():
    from capabilities.skill_parser import parse_skill_file
    from studio.paths import APP_ROOT
    path = os.path.join(APP_ROOT, 'skills', 'yf-door-panel-query', 'SKILL.md')
    if not os.path.isfile(path):
        pytest.skip('demo skill missing')
    parsed = parse_skill_file(path)
    assert parsed['name'] == 'yf-door-panel-query'
    assert 'strategy_id' in (parsed.get('inputs') or [])


def test_pipeline_validate_catalog():
    from orchestration.loader import load_pipeline_yaml, validate_pipeline
    from studio.paths import APP_ROOT
    path = os.path.join(APP_ROOT, 'iisp-catalog', 'pipelines', 'daily_ng_curation.yaml')
    if not os.path.isfile(path):
        pytest.skip('catalog pipeline missing')
    defn = load_pipeline_yaml(path)
    errs = validate_pipeline(defn)
    assert errs == []
