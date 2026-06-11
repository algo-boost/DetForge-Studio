"""Agent 对话输出 → Pipeline YAML 编译。"""
from __future__ import annotations

import json
import re

try:
    import yaml
except ImportError:
    yaml = None

from orchestration.pipeline_validate import validate_pipeline_any


def extract_yaml_from_text(text: str) -> str:
    """从 Agent 回复中提取 YAML 代码块。"""
    text = str(text or '')
    m = re.search(r'```(?:yaml|yml)\s*\n(.*?)```', text, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()
    if text.strip().startswith('id:'):
        return text.strip()
    return ''


def compile_agent_draft(text: str) -> dict:
    """解析 Agent 草稿，返回 {yaml, definition, errors}。"""
    raw_yaml = extract_yaml_from_text(text)
    if not raw_yaml:
        return {'success': False, 'error': '未找到 YAML 代码块', 'yaml': ''}
    if yaml is None:
        return {'success': False, 'error': '需要 PyYAML', 'yaml': raw_yaml}
    try:
        defn = yaml.safe_load(raw_yaml)
    except Exception as e:
        return {'success': False, 'error': f'YAML 解析失败: {e}', 'yaml': raw_yaml}
    if not isinstance(defn, dict):
        return {'success': False, 'error': 'Pipeline 必须是对象', 'yaml': raw_yaml}
    errors = validate_pipeline_any(defn)
    from orchestration.loader import pipeline_to_workflow_definition
    result: dict = {
        'success': len(errors) == 0,
        'yaml': raw_yaml,
        'pipeline': defn,
        'errors': errors,
        'engine': 'kestra' if defn.get('tasks') else 'legacy',
    }
    if defn.get('tasks'):
        result['definition'] = None
    else:
        result['definition'] = pipeline_to_workflow_definition(defn)
    return result


def build_agent_system_prompt(tools: list[dict]) -> str:
    """生成工作流助手 system prompt。"""
    tool_lines = []
    for t in tools[:40]:
        tool_lines.append(f"- {t.get('id')}: {t.get('label')} — {t.get('description', '')[:120]}")
    tools_block = '\n'.join(tool_lines) or '- （暂无注册工具）'
    return (
        '你是 IISP 工作流编排助手。根据用户需求生成 Pipeline YAML。\n'
        '语法要求：\n'
        '- 顶层字段：id, version, params_schema, nodes, edges（可选）\n'
        '- 每个 node：id, tool（Manifest id）, params, requires（可选）\n'
        '- params 支持模板 {{params.x}} 与 {{steps.stepId.key}}\n'
        '可用工具：\n'
        f'{tools_block}\n'
        '只输出一个 ```yaml 代码块，不要多余解释。'
    )
