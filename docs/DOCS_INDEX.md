# IISP 文档索引与现行标准

**更新**：2026-06-09 · **架构定稿**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) **Final v2.2**

> 所有文档冲突以 **IISP_DESIGN_FINAL v2.2** 为准。标记为「归档」的文档仅作历史参考。

---

## 现行标准（速查）

| 主题 | 定稿 |
|------|------|
| **编排** | **[Kestra](https://kestra.io) 唯一**（Edge 单机 + Hub 集群）；Flow 在 `iisp-catalog/pipelines/kestra/` |
| **废弃编排** | Windmill、cron 主编排、`iisp flow run` **生产**路径 |
| **本地 dev** | `iisp flow run` 仅 dry-run / CI |
| **Tool** | Contract v1 · `POST /v1/tools/{id}/invoke` · [`TOOL_PLUGIN_MODEL.md`](./TOOL_PLUGIN_MODEL.md) |
| **扩展 Tool** | **Skill-first**（L2）→ [`SKILL_PLATFORM.md`](./SKILL_PLATFORM.md) |
| **扩展 Pipeline** | Catalog YAML / Kestra Flow · **iisp-compose-flow** |
| **用户分层** | **L1** 交付/客户质检（只用）· **L2** SA/算法/光学（配置）· [`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) §2 |
| **前端** | React 19 + Vite 6 · 无 Electron/umi |
| **配置** | Git `iisp-catalog` + Provider |
| **设计态** | Cursor Skills + MCP（非运行时 LLM） |
| **变更记录** | [`PLATFORM_CHANGELOG.md`](./PLATFORM_CHANGELOG.md) · **iisp-record-platform-change** |
| **编码行为** | [Karpathy guidelines](https://github.com/forrestchang/andrej-karpathy-skills) · `.cursor/rules/karpathy-guidelines.mdc` |

---

## 文档分级

### 一级（必读）

| 文档 | 读者 |
|------|------|
| [`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) | 全员 — **唯一架构权威** |
| [`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) | 产品、L1/L2 角色、能力地图 |
| [`CODING_STANDARDS.md`](./CODING_STANDARDS.md) | 开发、PR、技术选型 |
| [`AGENTS.md`](../AGENTS.md) | Vibe / Cursor 贡献者 |

### 二级（专题）

| 文档 | 内容 |
|------|------|
| [`SKILL_PLATFORM.md`](./SKILL_PLATFORM.md) | L2 Skill → Tool 封装 |
| [`TOOL_PLUGIN_MODEL.md`](./TOOL_PLUGIN_MODEL.md) | 工具包终态 CLI+Skill+UI |
| [`TOOLBOX_ORCHESTRATION.md`](./TOOLBOX_ORCHESTRATION.md) | Kestra + Tool Contract 细则 |
| [`CATALOG_CENTER.md`](./CATALOG_CENTER.md) | Catalog Provider、同步 |
| [`SECURITY.md`](./SECURITY.md) | Token S1–S5 |
| [`IISP_PLATFORM.md`](./IISP_PLATFORM.md) | 部署、API 速查 |
| [`UI_REDESIGN_CHECKLIST.md`](./UI_REDESIGN_CHECKLIST.md) | 前端 U1–U5 |
| [`ARCHITECTURE_DIAGRAMS.md`](./ARCHITECTURE_DIAGRAMS.md) | 架构图集 |
| [`PLATFORM_CHANGELOG.md`](./PLATFORM_CHANGELOG.md) | **平台功能变更记录（必维护）** |
| [`PLATFORM_RISK_REGISTER.md`](./PLATFORM_RISK_REGISTER.md) | 风险登记 |

### 三级（流程/附录）

| 文档 | 内容 |
|------|------|
| [`SKILL_TO_TOOL.md`](./SKILL_TO_TOOL.md) | init-from-skill、L1–L4 |
| [`iisp-catalog/README.md`](../iisp-catalog/README.md) | Catalog 仓结构 |
| [`mcp/README.md`](../mcp/README.md) | MCP 设计态 |
| [`.cursor/skills/README.md`](../.cursor/skills/README.md) | 项目 Skills |

### 归档（勿作实现依据）

| 文档 | 说明 |
|------|------|
| [`ARCHITECTURE_FINAL.md`](./ARCHITECTURE_FINAL.md) | v1 定稿，已由 DESIGN_FINAL 取代 |
| [`ARCHITECTURE_GREENFIELD.md`](./ARCHITECTURE_GREENFIELD.md) | 绿场草案，含过时 Edge/cron 描述 |
| [`ARCHITECTURE_DECOUPLED.md`](./ARCHITECTURE_DECOUPLED.md) | 早期解耦设计 |
| [`AGENT_VIBE_CODING.md`](./AGENT_VIBE_CODING.md) | 已并入 DESIGN_FINAL Part VIII–X |

---

## Cursor Skills 索引

| Skill | 触发 |
|-------|------|
| **karpathy-guidelines** | 通用编码：简洁、surgical diff、可验证目标 |
| **iisp-skill-author** | L2：写 Platform Skill |
| **iisp-skill-pack** | Skill → 可加载 Tool |
| **iisp-compose-flow** | Kestra Flow / Pipeline |
| **iisp-create-tool** | 工程兜底：完整 Tool |
| **iisp-tool-package** | 标准工具包 |
| **iisp-vibe-guardrails** | 任何改动前 |
| **iisp-record-platform-change** | 平台功能变更 → changelog + 文档同步 |
| **iisp-review-pr** | PR 前（含 changelog 检查） |
| **iisp-platform-core** | 仅平台 Core |
| **iisp-secrets** | 密钥/Token |

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-09 | 安装 Karpathy guidelines（`.cursor/rules/karpathy-guidelines.mdc`） |
| 2026-06-09 | 新增 PLATFORM_CHANGELOG + iisp-record-platform-change 约束 |
| 2026-06-09 | 创建索引；对齐 v2.2 |
