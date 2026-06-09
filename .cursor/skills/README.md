# IISP 项目级 Cursor Skills

**标准**：[`docs/DOCS_INDEX.md`](../../docs/DOCS_INDEX.md) · [`docs/IISP_DESIGN_FINAL.md`](../../docs/IISP_DESIGN_FINAL.md) v2.2

本目录 Skills 在 **Vibe Coding** 时自动约束架构与编码规范。  
全局 Rules（`alwaysApply: true`）：[`iisp-core.mdc`](../rules/iisp-core.mdc) · [`karpathy-guidelines.mdc`](../rules/karpathy-guidelines.mdc)

## Skills 索引

| Skill | 何时触发 | 文档 |
|-------|----------|------|
| **iisp-skill-author** | **L2**：用业务语言新建 Platform Skill | [SKILL.md](./iisp-skill-author/SKILL.md) |
| **iisp-skill-pack** | Skill 封装为平台可加载 Tool | [SKILL.md](./iisp-skill-pack/SKILL.md) |
| **iisp-compose-flow** | **Kestra Flow** / Pipeline 编排 | [SKILL.md](./iisp-compose-flow/SKILL.md) |
| **karpathy-guidelines** | 通用编码行为（Karpathy 四条原则） | [SKILL.md](./karpathy-guidelines/SKILL.md) |
| **iisp-vibe-guardrails** | 任何 IISP 改动前 | [SKILL.md](./iisp-vibe-guardrails/SKILL.md) |
| **iisp-create-tool** | 工程兜底：完整 Capability Tool | [SKILL.md](./iisp-create-tool/SKILL.md) |
| **iisp-tool-package** | 标准工具包 CLI+Skill+可选 UI | [SKILL.md](./iisp-tool-package/SKILL.md) |
| **iisp-record-platform-change** | **平台功能变更** → changelog + 文档同步 | [SKILL.md](./iisp-record-platform-change/SKILL.md) |
| **iisp-review-pr** | 提交/审查 PR 前（含 changelog 检查） | [SKILL.md](./iisp-review-pr/SKILL.md) |
| **iisp-platform-core** | 仅改 Gateway/Registry/Catalog/MCP | [SKILL.md](./iisp-platform-core/SKILL.md) |
| **iisp-secrets** | 任何含密码/token/密钥 | [SKILL.md](./iisp-secrets/SKILL.md) |

## 推荐阅读顺序

**L1（交付 / 客户质检）** — 只用平台，不写 Skill/Flow

1. [`docs/PRODUCT_DESIGN.md`](../../docs/PRODUCT_DESIGN.md) §2、§4.1  
2. [`docs/USER_GUIDE.md`](../../docs/USER_GUIDE.md)（使用手册）

**L2（SA / 算法 / 光学）** — 配置与共建

1. [`docs/DOCS_INDEX.md`](../../docs/DOCS_INDEX.md)  
2. [`docs/SKILL_PLATFORM.md`](../../docs/SKILL_PLATFORM.md)  
3. **iisp-skill-author** → **iisp-skill-pack** → **iisp-compose-flow**

**平台工程**

1. [`docs/IISP_DESIGN_FINAL.md`](../../docs/IISP_DESIGN_FINAL.md)  
2. [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md)  
3. 按任务选上表 Skill  

## 文件级 Rules

| Rule | globs |
|------|-------|
| `iisp-core.mdc` | alwaysApply（IISP 架构） |
| `karpathy-guidelines.mdc` | alwaysApply（通用编码行为，[上游](https://github.com/forrestchang/andrej-karpathy-skills)） |
| `iisp-tools.mdc` | `tools/**`, `capabilities/**` |
| `iisp-pipelines.mdc` | `iisp-catalog/pipelines/**` |
| `iisp-changelog.mdc` | `server/**`, `frontend/**`, `tools/**`, `iisp-catalog/**` 等 |
| `iisp-frontend.mdc` | `frontend/**` |

**用户可见功能**改动完成后：**iisp-record-platform-change** → **iisp-review-pr**。

## MCP（设计态）

[`mcp/mcp.json.example`](../../mcp/mcp.json.example) — 实现后 Agent 可 list/validate。
