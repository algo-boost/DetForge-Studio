# Claude Code / Agent 入口

本仓库的 Agent 贡献指南见 **[`AGENTS.md`](./AGENTS.md)**（IDE 无关）。

快速自举：

```bash
./scripts/iisp agent context --json
```

| 资源 | 路径 |
|------|------|
| Skills | [`agent/skills/`](./agent/skills/README.md) |
| Rules | [`agent/rules/`](./agent/rules/README.md) |
| 接入说明 | [`agent/README.md`](./agent/README.md) |
| MCP 范例 | [`agent/mcp.json.example`](./agent/mcp.json.example) |

**设计态**：Agent 生成 Tool/Flow → validate → PR  
**运行态**：Kestra + Gateway invoke（无 LLM）
