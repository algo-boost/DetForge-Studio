"""iisp skill validate / pack CLI 测试。"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from cli.skill_pack import pack_skill, validate_skill
from studio.paths import APP_ROOT


@pytest.fixture
def demo_skill_path():
    path = Path(APP_ROOT) / 'skills' / 'yf-door-panel-query' / 'SKILL.md'
    if not path.is_file():
        pytest.skip('demo skill missing')
    return str(path)


def test_validate_skill_demo(demo_skill_path):
    result = validate_skill(demo_skill_path)
    assert 'name' in result
    assert result.get('name') == 'yf-door-panel-query'


def test_pack_skill_generates_manifest(demo_skill_path):
    with tempfile.TemporaryDirectory() as tmp:
        out = str(Path(tmp) / 'yf-door-panel-query')
        result = pack_skill(demo_skill_path, out)
        assert result.get('success'), result
        manifest = Path(out) / 'tool.manifest.json'
        assert manifest.is_file()
        data = json.loads(manifest.read_text(encoding='utf-8'))
        assert data.get('contract_version') == 'v1'
        assert data['entry']['invoke'] == '/v1/tools/yf-door-panel-query/invoke'
        assert (Path(out) / 'tests' / 'test_capability.py').is_file()


def test_skill_validate_cli(demo_skill_path):
    from cli.main import main
    code = main(['skill', 'validate', demo_skill_path])
    assert code in (0, 1)
