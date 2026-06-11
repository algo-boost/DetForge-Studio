# IISP Agent 贡献者指南

本仓库支持 **Vibe Coding**：自然语言 + **任意 coding agent** 新增 **Tool** 与 **Pipeline**，无需修改平台内核。

**IDE 无关配置根**：[`agent/`](agent/README.md) · 本文件为通用入口（Cursor / Claude Code / Codex / OpenClaw 等均适用）

**自动约束**：

- Rules：[`agent/rules/`](agent/rules/README.md)（Cursor 适配：`.cursor/rules/*.mdc`）
- Skills：[`agent/skills/`](agent/skills/README.md)（Cursor 适配：`.cursor/skills/` 符号链接）

**机器自举**（推荐任意 Agent 启动时执行一次）：

```bash
./scripts/iisp agent context --json
```

> **Karpathy 编码原则**：[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills) — Skill [`karpathy-guidelines`](agent/skills/karpathy-guidelines/SKILL.md)  
> **单元测试强制**：每实现功能须同 PR 交付测试 → Skill [**iisp-unit-tests**](agent/skills/iisp-unit-tests/SKILL.md)

---

## 文档体系（按序阅读）

| 优先级 | 文档 | 内容 |
|--------|------|------|
| 1 | [`docs/DOCS_INDEX.md`](docs/DOCS_INDEX.md) | **文档索引与现行标准 v2.2** |
| 2 | [`docs/SKILL_PLATFORM.md`](docs/SKILL_PLATFORM.md) | **L2 Skill-first** |
| 3 | [`docs/IISP_DESIGN_FINAL.md`](docs/IISP_DESIGN_FINAL.md) | 架构定稿 v2.2 |
| 4 | [`docs/CODING_STANDARDS.md`](docs/CODING_STANDARDS.md) | 编码规范、PR |
| 5 | [`docs/PRODUCT_DESIGN.md`](docs/PRODUCT_DESIGN.md) | L1/L2 角色、能力地图 |
| 6 | [`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md) | 架构图集 |
| 7 | [`docs/SECURITY.md`](docs/SECURITY.md) | Token 与安全 S1–S5 |
| 8 | [`docs/PLATFORM_RISK_REGISTER.md`](docs/PLATFORM_RISK_REGISTER.md) | 风险登记 |
| 9 | [`docs/IISP_PLATFORM.md`](docs/IISP_PLATFORM.md) | 部署与 API 速查 |

---

## 项目 Skills（Vibe 必用）

索引：[`agent/skills/README.md`](agent/skills/README.md) · [`agent/manifest.yaml`](agent/manifest.yaml)

| Skill | 用途 |
|-------|------|
| [`iisp-skill-author`](agent/skills/iisp-skill-author/SKILL.md) | **L2 默认**：写 Platform Skill |
| [`iisp-skill-pack`](agent/skills/iisp-skill-pack/SKILL.md) | **Skill → 可加载 Tool** |
| [`iisp-vibe-guardrails`](agent/skills/iisp-vibe-guardrails/SKILL.md) | **任何改动前**总约束 |
| [`iisp-compose-flow`](agent/skills/iisp-compose-flow/SKILL.md) | 新 Pipeline YAML |
| [`iisp-create-tool`](agent/skills/iisp-create-tool/SKILL.md) | 工程兜底、复杂 Tool |
| [`iisp-tool-package`](agent/skills/iisp-tool-package/SKILL.md) | 标准工具包 |
| [`iisp-record-platform-change`](agent/skills/iisp-record-platform-change/SKILL.md) | **功能变更必记** PLATFORM_CHANGELOG |
| [`iisp-review-pr`](agent/skills/iisp-review-pr/SKILL.md) | PR 前审查 |
| [`iisp-platform-core`](agent/skills/iisp-platform-core/SKILL.md) | 仅平台组改 Core |
| [`iisp-secrets`](agent/skills/iisp-secrets/SKILL.md) | 密钥/Token，禁止写进 Git/YAML |

---

## 变更记录（与代码同 PR）

用户可见功能、API、Tool、Flow、L1/L2 UI、部署或安全行为变更时：

1. 更新 [`docs/PLATFORM_CHANGELOG.md`](docs/PLATFORM_CHANGELOG.md) `[Unreleased]`
2. 遵循 Skill **iisp-record-platform-change**
3. **iisp-review-pr** 检查 changelog 是否齐全

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
./scripts/iisp agent context --json
./scripts/iisp tool validate tools/<id>/tool.manifest.json
./scripts/iisp workflow validate iisp-catalog/pipelines/<path>.yaml
```

---

## 设计态 vs 运行态

| | LLM / Agent | 说明 |
|---|-------------|------|
| **设计态** | ✅ | Agent 生成 YAML / 串 CLI 草稿 → validate → PR |
| **运行态（生产）** | ⚠️ | **Kestra** 或 API 触发；Agent 不直接写库 |
| **运行态（dev）** | ✅ | `iisp tool invoke` 链式验证 |

**Agent 编排协议（CLI-first）**：[`docs/AGENT_ORCHESTRATION.md`](docs/AGENT_ORCHESTRATION.md)

---

## MCP（任意支持 MCP 的 Agent）

[`agent/mcp.json.example`](agent/mcp.json.example) · [`mcp/README.md`](mcp/README.md)

规范：[`docs/IISP_DESIGN_FINAL.md`](docs/IISP_DESIGN_FINAL.md) Part IX

---

## IDE 快速接入

| Agent | 入口 |
|-------|------|
| **通用** | 本文件 + `agent/` |
| **Claude Code** | [`CLAUDE.md`](CLAUDE.md) |
| **Cursor** | `.cursor/skills/` + `.cursor/rules/`（适配层） |
| **Codex / OpenClaw** | `AGENTS.md` + MCP + `iisp agent context` |

详见 [`agent/README.md`](agent/README.md)
