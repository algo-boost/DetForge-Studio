"""Agent 自举上下文（IDE 无关）：Skills、Rules、CLI、MCP 入口。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from studio.paths import APP_ROOT

AGENT_ROOT = Path(APP_ROOT) / 'agent'
SKILLS_ROOT = AGENT_ROOT / 'skills'
RULES_ROOT = AGENT_ROOT / 'rules'
MANIFEST_FILE = AGENT_ROOT / 'manifest.yaml'


def _parse_skill_frontmatter(text: str) -> dict[str, str]:
    m = re.match(r'^---\s*\n(.*?)\n---', text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ':' not in line:
            continue
        key, _, val = line.partition(':')
        out[key.strip()] = val.strip().strip('"').strip("'")
    return out


def discover_skills() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not SKILLS_ROOT.is_dir():
        return rows
    for skill_dir in sorted(SKILLS_ROOT.iterdir()):
        skill_md = skill_dir / 'SKILL.md'
        if not skill_dir.is_dir() or not skill_md.is_file():
            continue
        meta = _parse_skill_frontmatter(skill_md.read_text(encoding='utf-8'))
        rows.append({
            'id': meta.get('name') or skill_dir.name,
            'path': str(skill_md.relative_to(APP_ROOT)),
            'description': meta.get('description') or '',
            'tags': meta.get('tags') or '',
        })
    return rows


def discover_rules() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not RULES_ROOT.is_dir():
        return rows
    for rule_file in sorted(RULES_ROOT.glob('*.md')):
        if rule_file.name == 'README.md':
            continue
        rows.append({
            'id': rule_file.stem,
            'path': str(rule_file.relative_to(APP_ROOT)),
        })
    return rows


def build_agent_context() -> dict[str, Any]:
    return {
        'version': '1.0',
        'entrypoints': {
            'agents_md': 'AGENTS.md',
            'manifest': 'agent/manifest.yaml',
            'skills_index': 'agent/skills/README.md',
            'agent_readme': 'agent/README.md',
        },
        'skills': discover_skills(),
        'rules': discover_rules(),
        'cli': {
            'agent_context': './scripts/iisp agent context --json',
            'tool_list': './scripts/iisp tool list',
            'tool_invoke': './scripts/iisp tool invoke <tool_id> --param key=value',
            'tool_run': './scripts/iisp tool run <tool_id>   # manifest entry.cli 子进程',
            'tool_validate': './scripts/iisp tool validate [path/to/tool.manifest.json]',
            'workflow_validate': './scripts/iisp workflow validate <path/to/flow.yaml>',
            'flow_list_kestra': './scripts/iisp flow list-kestra',
            'flow_execute': './scripts/iisp flow execute <flow_id> --param key=value',
            'flow_status': './scripts/iisp flow status <run_key>',
            'flow_resume': './scripts/iisp flow resume <run_key>',
            'flow_export_shell': './scripts/iisp flow export-shell <flow_id> [-o script.sh]',
            'catalog_sync': './scripts/iisp catalog sync',
        },
        'agent_orchestration_doc': 'docs/AGENT_ORCHESTRATION.md',
        'compose_flow_skill': 'agent/skills/iisp-compose-flow/SKILL.md',
        'flow_yaml_comments': 'docs/FLOW_YAML_COMMENTS.md',
        'mcp': {
            'example_config': 'agent/mcp.json.example',
            'legacy_cursor_config': 'mcp/mcp.json.example',
            'server': 'mcp/iisp_server.py',
            'tools': [
                'iisp_list_tools',
                'iisp_get_tool',
                'iisp_validate_manifest',
                'iisp_validate_pipeline',
                'iisp_list_pipelines',
                'iisp_init_tool_from_skill',
                'iisp_agent_context',
                'iisp_invoke',
            ],
            'invoke_requires': 'IISP_ENV=dev 且 IISP_AGENT_ALLOW_INVOKE=1',
        },
        'design_vs_runtime': {
            'design': 'Agent 生成/校验 Tool、Flow、Skill 文件 → Git PR',
            'runtime': 'Kestra + POST /v1/tools/{id}/invoke（无 LLM）',
        },
    }
