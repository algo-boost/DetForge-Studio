---
name: iisp-vibe-guardrails
description: >-
  Enforces IISP architecture guardrails for any code change in DetForge-Studio.
  Use when editing IISP, vibe coding, adding features, fixing bugs, or before
  any PR — ensures Tool Contract, Catalog pipelines, and no workflow_engine hacks.
---

# IISP Vibe Guardrails（总约束）

在 **任何** IISP 仓库改动前，先确认本文 + [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md) + **karpathy-guidelines**（最小 diff、不过度设计）。

## 30 秒自检

1. 这是 **新业务能力** 吗？→ 应走 **Tool + Pipeline PR**，不是改 Platform 调度  
2. 这是 **组合/定时/顺序** 吗？→ **Kestra Flow**（`pipelines/kestra/`）或设计态 DSL，不写 Python 链  
3. 是否只通过 **HTTP invoke** 集成？→ 禁止编排 `import studio.*`  
4. 改动路径在 **允许列表** 内吗？→ 见 CODING_STANDARDS §2.2  
5. 能否 **`validate`**？→ Tool / Pipeline 必须过 CLI  
6. **用户可见吗？**→ 是则 **iisp-record-platform-change** 更新 `PLATFORM_CHANGELOG.md`  
7. **有单元测试吗？**→ 运行时代码必须与功能 **同 PR** 交付测试（**iisp-unit-tests**）

## 允许 vs 禁止

| ✅ 允许 | ❌ 禁止 |
|--------|--------|
| `tools/<id>/` 新 Tool | 扩展 `workflow_engine` |
| `iisp-catalog/pipelines/kestra/*.yaml` | `workflow_scheduler`、cron 主编排 |
| `skills/*/SKILL.md` | Gateway 内业务 if-else |
| `frontend/` UI（符合规范） | Tool 互 import service |
| `tests/` 与功能同 PR | 无测试的功能 PR、「后续再补测试」、跳过 validate 合并 |
| 平台组：`core/`、`gateway/`（见 iisp-platform-core） | 运行态 LLM 调度 |

## 文档优先级

1. [`docs/IISP_DESIGN_FINAL.md`](../../docs/IISP_DESIGN_FINAL.md)  
2. [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md)  
3. [`docs/ARCHITECTURE_DIAGRAMS.md`](../../docs/ARCHITECTURE_DIAGRAMS.md)  

## 该用哪个 Skill？

| 用户意图 | Skill |
|----------|-------|
| 新工具/封装能力 | `iisp-create-tool` |
| 编排/定时/组合 | `iisp-compose-flow` |
| 改 Gateway/Registry/sync | `iisp-platform-core` |
| 提交 PR 前 | `iisp-review-pr` |
| **写/改功能逻辑** | **`iisp-unit-tests`** |
| **平台功能变更** | **`iisp-record-platform-change`** |

## 设计态 vs 运行态

- **设计态**：Cursor 生成文件 → validate → PR（可用 LLM）  
- **运行态**：**Kestra** + invoke（**无 LLM**）

## 完成后必跑（如适用）

```bash
./scripts/iisp tool validate ...
./scripts/iisp workflow validate ...
python -m pytest <本次改动相关 tests> -q   # 强制，见 iisp-unit-tests
```
