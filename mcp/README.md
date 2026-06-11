# IISP MCP Server

**设计态 Agent 接口**（IDE 无关）：供 Cursor、Claude Code、Codex、OpenClaw 等列出工具、校验 Manifest/Pipeline。

**规范**：[`docs/IISP_DESIGN_FINAL.md`](../docs/IISP_DESIGN_FINAL.md) Part IX

## 配置范例

| 文件 | 用途 |
|------|------|
| [`agent/mcp.json.example`](../agent/mcp.json.example) | **推荐** — 通用 MCP 客户端 |
| [`mcp.json.example`](./mcp.json.example) | 兼容旧路径（内容相同） |

各 IDE 将范例复制到自身 MCP 配置路径即可（如 Cursor → `.cursor/mcp.json`）。

## 无 MCP 时的等价 CLI

```bash
./scripts/iisp agent context --json
./scripts/iisp tool validate ...
./scripts/iisp workflow validate ...
```

## 启用

1. 依赖：`pip install mcp`（或使用已装 MCP SDK 的 Python 环境）
2. 将 [`agent/mcp.json.example`](../agent/mcp.json.example) 复制到 IDE MCP 配置（如 `.cursor/mcp.json`）
3. `cwd` 指向 **DetForge-Studio 根目录**（含 `scripts/iisp`）
4. 默认 `IISP_ENV=dev`、`IISP_AGENT_ALLOW_INVOKE=0`（禁止 Agent 直接 invoke）

```bash
# 本地冒烟（stdio 会挂起等待客户端，仅验证能 import）
python mcp/iisp_server.py
```

## Tools 列表

| 工具 | 说明 |
|------|------|
| `iisp_list_tools` | 已注册 tool_id + params_schema |
| `iisp_get_tool` | 完整 Manifest |
| `iisp_validate_manifest` | path 或 json |
| `iisp_validate_pipeline` | path 或 yaml（含 Kestra tasks） |
| `iisp_list_pipelines` | Catalog 列表 |
| `iisp_init_tool_from_skill` | SKILL → 工具骨架 |
| `iisp_agent_context` | 等价 `iisp agent context` |
| `iisp_invoke` | dev-only，需 `IISP_AGENT_ALLOW_INVOKE=1` |

详见 [`docs/IISP_DESIGN_FINAL.md`](../docs/IISP_DESIGN_FINAL.md) Part IX。
