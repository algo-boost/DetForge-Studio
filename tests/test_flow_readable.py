"""Flow 可读化：YAML 注释 → 表单字段。"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WELCOME_YAML = ROOT / 'iisp-catalog' / 'pipelines' / 'demo' / 'welcome_flow.yaml'


def test_parse_yaml_step_comments_welcome():
    from orchestration.flow_readable import parse_yaml_step_comments

    if not WELCOME_YAML.is_file():
        return
    text = WELCOME_YAML.read_text(encoding='utf-8')
    meta = parse_yaml_step_comments(text)
    assert isinstance(meta, dict)


def test_build_node_readable_minimal():
    from orchestration.flow_readable import build_node_readable

    node = {
        'id': 'query',
        'tool_id': 'smoke-query',
        'tool': {
            'label': '冒烟查询',
            'outputs': ['task_id'],
        },
    }
    readable = build_node_readable(node, yaml_meta={}, flow_inputs=set())
    assert readable['inputs'] is not None
    assert readable['outputs'] is not None
