---
name: iisp-skill-author
description: >-
  Writes IISP Platform Skill v1 (SKILL.md) for non-professional tool authors.
  Use when the user wants a new tool in plain language, export/import automation,
  or business workflow without coding Flask/React — output is skills/id/SKILL.md only.
---

# IISP 平台 Skill 创作（L2 配置者）

**读者**：SA、算法、光学 — 在 **Agent 会话**中扩展平台能力；**不是**交付/客户质检使用手册。  
**规范**：[`docs/SKILL_PLATFORM.md`](../../docs/SKILL_PLATFORM.md) · [`docs/PRODUCT_DESIGN.md`](../../docs/PRODUCT_DESIGN.md) §2

## 你只产出

- **`skills/<tool_id>/SKILL.md`**（Platform Skill v1）
- 可选：**一个 Python 脚本**（`kind: script` 时，放在 Skill 同目录 `scripts/`）

**不要**直接改：`server/`、`workflow_engine`、`frontend/` 大段 React、Gateway。

## Platform Skill v1 模板

```markdown
---
name: my-tool-id
description: 一句话。Use when 用户需要……
version: "0.1.0"
tags: [query]
ui_level: schema
---

# 中文标题

## 何时使用

（业务语言）

## 输入

- field_a: 说明，必填
- field_b: 说明，可选

## 输出

- result_id
- count

## 产物

- csv

## 实现

kind: script
script: scripts/my_script.py

## UI

mode: schema

## 步骤

1. …
2. …
```

## 实现 kind 选择（帮用户选最简单的）

| 用户需求 | kind |
|----------|------|
| 简单脚本、改几行 Python | **script** |
| 要调 DB、复杂逻辑 | **capability**（需 Agent 帮写 service.py，或转专业同事） |
| 已有独立 HTTP 服务 | **http** + url |

**默认推荐 script**，配 `lib/iisp-skill-sdk`（规划）。

## script 脚本模板

```python
"""由 Skill 描述；pack 后自动接入 CLI。"""
import json, sys

def main(params, inputs):
    # 只写业务
    return {"status": "done", "outputs": {"result_id": "1", "count": 0}}

if __name__ == "__main__":
    payload = json.loads(sys.stdin.read() or "{}")
    params = payload.get("params") or {}
    inputs = payload.get("inputs") or {}
    out = main(params, inputs)
    print(json.dumps(out, ensure_ascii=False))
```

## 完成后告诉用户

```bash
./scripts/iisp tool init-from-skill skills/<id>/SKILL.md --out tools/<id>/
./scripts/iisp tool validate tools/<id>/tool.manifest.json
# 规划：iisp skill pack skills/<id>/SKILL.md
```

然后走 **iisp-skill-pack** 或 **iisp-review-pr**。

## 禁止

- Skill 里写数据库密码、api_token
- 编造未在 `## 输出` 声明的字段
- 要求用户学 Kestra — 编排交给 **iisp-compose-flow**

## 与 Cursor 创作 Skill 的区别

本文档产出的是 **平台 Skill（交付物）**；`.cursor/skills/iisp-skill-author` 是 **教 Agent 怎么写交付物**。
