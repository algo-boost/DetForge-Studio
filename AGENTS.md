# IISP Agent 贡献者指南

本仓库支持 **Vibe Coding**：自然语言 + Cursor Agent 新增 **Tool** 与 **Pipeline**，无需修改平台内核。

**自动约束**：Cursor Rule [`.cursor/rules/iisp-core.mdc`](.cursor/rules/iisp-core.mdc) + 项目 Skills [`.cursor/skills/`](.cursor/skills/README.md)

---

## 文档体系（按序阅读）

| 优先级 | 文档 | 内容 |
|--------|------|------|
| 1 | [`docs/SKILL_PLATFORM.md`](docs/SKILL_PLATFORM.md) | **Skill-first（非专业主路径）** |
| 2 | [`docs/IISP_DESIGN_FINAL.md`](docs/IISP_DESIGN_FINAL.md) | 架构定稿 |
| 3 | [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) | **编码规范、技术选型、PR** |
| [`docs/PRODUCT_DESIGN.md`](docs/PRODUCT_DESIGN.md) | **角色 L1/L2、能力地图** |
| 5 | [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) | **架构图集** |
| 6 | [`docs/SECURITY.md`](docs/SECURITY.md) | **Token 与安全 S1–S5** |
| 7 | [`docs/PLATFORM_RISK_REGISTER.md`](docs/PLATFORM_RISK_REGISTER.md) | **遗漏与风险登记** |
| 8 | [`docs/IISP_PLATFORM.md`](docs/IISP_PLATFORM.md) | 部署与 API 速查 |

---

## 项目 Skills（Vibe 必用）

| Skill | 用途 |
|-------|------|
| [`iisp-skill-author`](.cursor/skills/iisp-skill-author/SKILL.md) | **非专业默认**：只写 Platform Skill |
| [`iisp-skill-pack`](.cursor/skills/iisp-skill-pack/SKILL.md) | **Skill → 可加载 Tool**（Manifest/CLI/UI） |
| [`iisp-vibe-guardrails`](.cursor/skills/iisp-vibe-guardrails/SKILL.md) | **任何改动前**总约束 |
| [`iisp-compose-flow`](.cursor/skills/iisp-compose-flow/SKILL.md) | 新 Pipeline YAML |
| [`iisp-create-tool`](.cursor/skills/iisp-create-tool/SKILL.md) | 工程兜底、复杂 Tool |
| [`iisp-tool-package`](.cursor/skills/iisp-tool-package/SKILL.md) | 标准工具包（CLI+Skill+可选 UI） |
| [`iisp-review-pr`](.cursor/skills/iisp-review-pr/SKILL.md) | PR 前审查 |
| [`iisp-platform-core`](.cursor/skills/iisp-platform-core/SKILL.md) | 仅平台组改 Core |
| [`iisp-secrets`](.cursor/skills/iisp-secrets/SKILL.md) | 密钥/Token，禁止写进 Git/YAML |

索引：[`.cursor/skills/README.md`](.cursor/skills/README.md)

---

## 两条 Vibe 路径

**新 Tool（默认 Skill-first）**

```text
业务描述 → iisp-skill-author → skills/<id>/SKILL.md
         → iisp-skill-pack    → tools/<id>/ → validate → PR
```

**新 Pipeline**

```text
iisp-compose-flow → iisp-catalog/pipelines/**/*.yaml → validate → Catalog PR
```

| 意图 | 产出 | 校验 | PR |
|------|------|------|-----|
| 新 Tool | `skills/` → `tools/<id>/` | `iisp tool validate` | 主仓 |
| 新 Pipeline | `iisp-catalog/pipelines/**/*.yaml` | `iisp workflow validate` | Catalog 仓 |

---

## Agent 禁止

- 修改 `workflow_engine`、`workflow_scheduler`、Platform Gateway 组合逻辑  
- Tool 之间互相 import `service.py`  
- 跳过 validate 合并  
- 生产环境通过 Agent/MCP invoke 写库（仅 dev + 显式 flag）
- 在 Catalog、代码、示例中硬编码 password/token（用 **iisp-secrets**）

---

## 自检

```bash
./scripts/iisp tool validate tools/<id>/tool.manifest.json
./scripts/iisp workflow validate iisp-catalog/pipelines/<path>.yaml
./scripts/iisp agent context --json    # A2 规划
```

---

## 设计态 vs 运行态

| | LLM | 说明 |
|---|-----|------|
| **设计态** | ✅ | Cursor 生成文件 → validate → PR |
| **运行态** | ❌ | cron / Kestra + HTTP invoke |

---

## MCP

[`mcp/README.md`](mcp/README.md) · [`mcp/mcp.json.example`](mcp/mcp.json.example)
