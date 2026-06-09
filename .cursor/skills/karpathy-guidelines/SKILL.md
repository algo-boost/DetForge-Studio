---
name: karpathy-guidelines
description: >-
  Behavioral guidelines to reduce common LLM coding mistakes (Karpathy-inspired).
  Use when writing, reviewing, or refactoring any code in this repo — complements
  IISP rules with simplicity, surgical diffs, and verifiable success criteria.
license: MIT
metadata:
  upstream: https://github.com/forrestchang/andrej-karpathy-skills
---

# Karpathy Guidelines（项目内）

上游：[forrestchang/andrej-karpathy-skills](https://github.com/forrestchang/andrej-karpathy-skills)

Cursor 已通过 [`.cursor/rules/karpathy-guidelines.mdc`](../../rules/karpathy-guidelines.mdc) 自动加载（`alwaysApply: true`）。本 Skill 供 Agent 显式引用或与 IISP Skills 联用。

## 与 IISP 的关系

| 场景 | 优先 |
|------|------|
| 最小 diff、不过度抽象、先问清再写 | **Karpathy** |
| Kestra、Tool Contract、Catalog、changelog | **IISP**（`iisp-vibe-guardrails`） |

## 四条原则（摘要）

1. **Think Before Coding** — 假设写清、不确定就问  
2. **Simplicity First** — 只写请求范围内的最少代码  
3. **Surgical Changes** — 不改无关代码；每行 diff 能追溯到需求  
4. **Goal-Driven Execution** — 可验证的成功标准 + 分步 verify  

完整条文见 `karpathy-guidelines.mdc` 或上游 `CLAUDE.md`。

## 完成后（IISP 仓库额外）

```bash
./scripts/iisp tool validate ...      # 若改 Tool
./scripts/iisp workflow validate ...  # 若改 Flow
python -m pytest ... -q               # 若改逻辑
```

用户可见功能 → **iisp-record-platform-change**。
