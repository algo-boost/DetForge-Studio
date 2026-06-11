# IISP 项目 Skills（IDE 无关）

**权威目录**：`agent/skills/`（本目录）

**标准**：[`docs/DOCS_INDEX.md`](../../docs/DOCS_INDEX.md) · [`docs/IISP_DESIGN_FINAL.md`](../../docs/IISP_DESIGN_FINAL.md) v2.2

任意 Agent（Cursor、Claude Code、Codex、OpenClaw 等）均可读取本目录下 `SKILL.md`。  
Cursor 用户：`.cursor/skills/` 为指向本目录的符号链接，无需重复维护。

**机器索引**：`./scripts/iisp agent context --json`

## Skills 索引

| Skill | 何时触发 | 文档 |
|-------|----------|------|
| **iisp-skill-author** | **L2**：用业务语言新建 Platform Skill | [SKILL.md](./iisp-skill-author/SKILL.md) |
| **iisp-skill-pack** | Skill 封装为平台可加载 Tool | [SKILL.md](./iisp-skill-pack/SKILL.md) |
| **iisp-compose-flow** | **Kestra Flow** / Pipeline 编排 | [SKILL.md](./iisp-compose-flow/SKILL.md) |
| **karpathy-guidelines** | 通用编码行为 | [SKILL.md](./karpathy-guidelines/SKILL.md) |
| **iisp-vibe-guardrails** | 任何 IISP 改动前 | [SKILL.md](./iisp-vibe-guardrails/SKILL.md) |
| **iisp-unit-tests** | 功能实现必写单元测试（同 PR） | [SKILL.md](./iisp-unit-tests/SKILL.md) |
| **iisp-create-tool** | 工程兜底：完整 Capability Tool | [SKILL.md](./iisp-create-tool/SKILL.md) |
| **iisp-tool-package** | 标准工具包 CLI+Skill+可选 UI | [SKILL.md](./iisp-tool-package/SKILL.md) |
| **iisp-record-platform-change** | 平台功能变更 → changelog | [SKILL.md](./iisp-record-platform-change/SKILL.md) |
| **iisp-review-pr** | 提交/审查 PR 前 | [SKILL.md](./iisp-review-pr/SKILL.md) |
| **iisp-platform-core** | 仅改 Gateway/Registry/Catalog/MCP | [SKILL.md](./iisp-platform-core/SKILL.md) |
| **iisp-secrets** | 任何含密码/token/密钥 | [SKILL.md](./iisp-secrets/SKILL.md) |

## 规则（Rules）

可移植 Markdown：[`../rules/`](../rules/README.md)  
Cursor 适配：`.cursor/rules/*.mdc`

## MCP（设计态）

[`../mcp.json.example`](../mcp.json.example) · [`../../mcp/README.md`](../../mcp/README.md)
