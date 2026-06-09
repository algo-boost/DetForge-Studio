"""Flow runner 与演示工具测试。"""
from __future__ import annotations

import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


def test_welcome_demo_flow_auto_resume():
    from orchestration.flow_runner import find_pipeline, run_flow

    defn, _path = find_pipeline('welcome_demo')
    result = run_flow(defn, {'reviewer': 'pytest'}, auto_resume=True)
    assert result.status == 'done'
    assert len(result.steps) == 4
    assert result.steps[0].tool == 'demo-query'
    assert result.steps[0].outputs.get('task_id', '').startswith('demo-task-')
    assert result.steps[-1].tool == 'demo-notify'


def test_welcome_demo_flow_pauses_without_auto_resume():
    from orchestration.flow_runner import find_pipeline, run_flow

    defn, _path = find_pipeline('welcome_demo')
    result = run_flow(defn, {'reviewer': 'pytest'}, auto_resume=False)
    assert result.status == 'waiting_human'
    assert result.pause_at == 'approve'
    assert len(result.steps) == 3


def test_resolve_templates():
    from orchestration.flow_runner import resolve_templates

    params = {'reviewer': 'alice'}
    steps = {'query': {'task_id': 't-1', 'row_count': 5}}
    assert resolve_templates('{{params.reviewer}}', params, steps) == 'alice'
    assert resolve_templates('{{steps.query.task_id}}', params, steps) == 't-1'
    assert resolve_templates(
        {'task_id': '{{steps.query.task_id}}'},
        params,
        steps,
    ) == {'task_id': 't-1'}
