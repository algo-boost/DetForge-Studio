# IISP 项目级 Cursor Skills

本目录 Skills 在 **Vibe Coding** 时自动约束架构与编码规范。  
全局 Rule： [`.cursor/rules/iisp-core.mdc`](../rules/iisp-core.mdc)（`alwaysApply: true`）

## Skills 索引

| Skill | 何时触发 | 文档 |
|-------|----------|------|
| **iisp-skill-author** | **非专业**：用业务语言新建工具，只写 Platform Skill | [SKILL.md](./iisp-skill-author/SKILL.md) |
| **iisp-skill-pack** | Skill 已写好，**封装为平台可加载 Tool** | [SKILL.md](./iisp-skill-pack/SKILL.md) |
| **iisp-vibe-guardrails** | 任何 IISP 改动、不确定能否改某文件 | [SKILL.md](./iisp-vibe-guardrails/SKILL.md) |
| **iisp-compose-flow** | 编排、定时、组合查询/质检/归档 | [SKILL.md](./iisp-compose-flow/SKILL.md) |
| **iisp-create-tool** | 工程兜底：完整 Capability / 复杂 Tool | [SKILL.md](./iisp-create-tool/SKILL.md) |
| **iisp-tool-package** | 标准工具包 CLI+Skill+可选 UI | [SKILL.md](./iisp-tool-package/SKILL.md) |
| **iisp-review-pr** | 提交/审查 PR 前 | [SKILL.md](./iisp-review-pr/SKILL.md) |
| **iisp-platform-core** | 仅改 Gateway/Registry/Catalog/MCP | [SKILL.md](./iisp-platform-core/SKILL.md) |
| **iisp-secrets** | 任何含密码/token/密钥的生成 | [SKILL.md](./iisp-secrets/SKILL.md) |

## 推荐阅读顺序

**非专业 / 业务贡献者**

1. [`docs/SKILL_PLATFORM.md`](../../docs/SKILL_PLATFORM.md)  
2. **iisp-skill-author** → **iisp-skill-pack** → **iisp-compose-flow**（如需定时）  

**工程 / 平台**

1. [`AGENTS.md`](../../AGENTS.md)  
2. [`docs/IISP_DESIGN_FINAL.md`](../../docs/IISP_DESIGN_FINAL.md)  
3. [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md)  
4. 按任务选上表 Skill  

## 文件级 Rules

| Rule | globs |
|------|-------|
| `iisp-core.mdc` | alwaysApply |
| `iisp-tools.mdc` | `tools/**`, `capabilities/**` |
| `iisp-pipelines.mdc` | `iisp-catalog/pipelines/**` |
| `iisp-frontend.mdc` | `frontend/**` |

## MCP（设计态）

[`mcp/mcp.json.example`](../../mcp/mcp.json.example) — 实现后 Agent 可 list/validate。
