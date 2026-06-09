# IISP MCP Server

设计态 Agent 接口，供 Cursor 列出工具、校验 Manifest/Pipeline。

**规范**：[`docs/IISP_DESIGN_FINAL.md`](../docs/IISP_DESIGN_FINAL.md) Part IX

## 启用（规划）

1. 复制 `mcp.json.example` → `.cursor/mcp.json`（或合并到用户 MCP 配置）
2. 实现 `iisp_server.py`（A4 里程碑）
3. 确保 `IISP_ENV=dev`；生产禁止 `IISP_AGENT_ALLOW_INVOKE`

## Tools 列表

见设计文档 §9.2：`iisp_list_tools`、`iisp_validate_pipeline` 等。
