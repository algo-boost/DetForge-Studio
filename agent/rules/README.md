# Agent 规则（IDE 无关）

本目录为**可移植 Markdown 规则**，供 Claude Code、Codex、OpenClaw、Cursor 等任意 Agent 读取。

| 文件 | 作用域 |
|------|--------|
| [`iisp-core.md`](./iisp-core.md) | 全局架构约束 |
| [`iisp-tools.md`](./iisp-tools.md) | `tools/**`、`capabilities/**` |
| [`iisp-pipelines.md`](./iisp-pipelines.md) | `iisp-catalog/pipelines/**` |

## IDE 适配层

| IDE / Agent | 如何加载本目录 |
|-------------|----------------|
| **任意** | 读 [`AGENTS.md`](../AGENTS.md) + `./scripts/iisp agent context --json` |
| **Cursor** | [`.cursor/rules/*.mdc`](../.cursor/rules/)（globs + alwaysApply） |
| **Claude Code** | `CLAUDE.md` → `AGENTS.md`；可将 `agent/rules/` 加入项目说明 |
| **Codex / OpenClaw** | `AGENTS.md` + MCP（[`agent/mcp.json.example`](./mcp.json.example)） |
| **MCP 客户端** | 连接 `mcp/iisp_server.py`（规划 A4） |

Cursor 的 `.mdc` 为 **适配器**，内容与 `agent/rules/` 保持语义一致，不单独维护第二套业务规则。
