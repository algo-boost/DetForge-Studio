#!/usr/bin/env python3
"""IISP MCP Server — stdio，供 Cursor / Claude Code 等 Agent 自举编排。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from mcp.server.fastmcp import FastMCP

from orchestration.agent_context import build_agent_context
from orchestration.agent_mcp_api import (
    get_tool_manifest,
    init_tool_from_skill_for_agent,
    invoke_tool_for_agent,
    list_pipelines_for_agent,
    list_tools_for_agent,
    validate_manifest_for_agent,
    validate_pipeline_for_agent,
)

mcp = FastMCP(
    'iisp',
    instructions=(
        'IISP 编排 Agent 接口：列出已注册工具、校验 Manifest/Pipeline、'
        '读取 agent context。生产写操作请走 Git PR；dev 可选 iisp_invoke。'
    ),
)


def _json_text(data: object) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool(name='iisp_list_tools')
def iisp_list_tools(tag: str | None = None) -> str:
    """列出 Registry 已注册工具（编排前必调）。可选 tag 过滤 id/label/tags。"""
    return _json_text(list_tools_for_agent(tag=tag))


@mcp.tool(name='iisp_get_tool')
def iisp_get_tool(tool_id: str) -> str:
    """按 tool_id 返回完整 tool.manifest.json。"""
    return _json_text(get_tool_manifest(tool_id))


@mcp.tool(name='iisp_validate_manifest')
def iisp_validate_manifest(path: str | None = None, json: str | None = None) -> str:
    """校验 Tool Manifest（path 或 json 二选一）。"""
    return _json_text(validate_manifest_for_agent(path=path, json_text=json))


@mcp.tool(name='iisp_validate_pipeline')
def iisp_validate_pipeline(path: str | None = None, yaml: str | None = None) -> str:
    """校验 Pipeline / Kestra Flow YAML（path 或 yaml 二选一）。"""
    return _json_text(validate_pipeline_for_agent(path=path, yaml_text=yaml))


@mcp.tool(name='iisp_list_pipelines')
def iisp_list_pipelines(catalog: str = 'repo') -> str:
    """列出 Catalog 中的 Pipeline（legacy + kestra）。"""
    return _json_text(list_pipelines_for_agent(catalog=catalog))


@mcp.tool(name='iisp_init_tool_from_skill')
def iisp_init_tool_from_skill(skill_path: str, out_dir: str) -> str:
    """从 SKILL.md 生成工具包骨架到 out_dir。"""
    return _json_text(init_tool_from_skill_for_agent(skill_path, out_dir))


@mcp.tool(name='iisp_agent_context')
def iisp_agent_context() -> str:
    """等价 ./scripts/iisp agent context — Skills、CLI、MCP 入口。"""
    return _json_text(build_agent_context())


@mcp.tool(name='iisp_invoke')
def iisp_invoke(
    tool_id: str,
    params: dict | None = None,
    run_id: str = 'mcp-agent',
    step_id: str = 'main',
) -> str:
    """dev-only 调用工具（需 IISP_ENV=dev 且 IISP_AGENT_ALLOW_INVOKE=1）。"""
    try:
        payload = invoke_tool_for_agent(
            tool_id,
            params=params,
            run_id=run_id,
            step_id=step_id,
        )
    except PermissionError as exc:
        return _json_text({'error': str(exc)})
    except ValueError as exc:
        return _json_text({'status': 'failed', 'error': str(exc)})
    return _json_text(payload)


if __name__ == '__main__':
    mcp.run()
