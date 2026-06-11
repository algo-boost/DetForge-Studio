---
name: iisp-create-tool
description: Create a new IISP Tool from natural language. Use when the user wants to add a capability, wrap a script, register a tool, or extend the toolbox with tool.manifest.json and invoke contract v1.
---

# IISP — 新增 Tool（Vibe Coding）

## 何时使用

用户要：**新增工具**、**封装脚本**、**注册 Capability** — 且 **Skill 路径不够**（需 custom UI / 复杂 service）时。

> **默认先走** **iisp-skill-author** → **iisp-skill-pack**（L2）。本 Skill 为工程兜底。

## 必读约束

1. 先读 **iisp-vibe-guardrails** Skill 与 [`docs/CODING_STANDARDS.md`](../../../docs/CODING_STANDARDS.md)  
2. 阅读 [`AGENTS.md`](../../../AGENTS.md) 与 [`docs/IISP_DESIGN_FINAL.md`](../../../docs/IISP_DESIGN_FINAL.md) Part V、Part VI。  
2. **禁止**修改 `workflow_engine`、`server/` Gateway 组合逻辑、其他 Tool 的 `service.py`。  
3. 跨模块只通过 **Tool Contract v1**；业务在 `service.py`，`invoke.py` 只做映射。

## 工作流（按顺序）

### 1. 澄清（简短）

- 工具 `id`（小写连字符，如 `sn-batch-query`）  
- 输入 params、输出 outputs、是否产生 artifacts  
- 是否依赖 DB（只用 `lib/platform`）

### 2. 写 SKILL

路径：`skills/<scene>/SKILL.md`

```markdown
---
name: <tool-id>
description: 一句话。Use when 用户需要…
---

# 标题

## 输入
- param_a: 说明

## 输出
- field_b

## 实现说明
（步骤摘要）
```

### 3. 脚手架

```bash
./scripts/iisp tool init-from-skill skills/<scene>/SKILL.md --out tools/<tool-id>
```

若 `tools/` 不存在，可用 `capabilities/` 或 `--out packages/<name>`（与团队约定一致）。

### 4. 实现

- `tool.manifest.json`：`id` = skill `name`，`contract_version: v1`  
- `invoke.py`：`handle(body) -> ToolResult`，status 为 `done|failed|waiting_human|skipped`  
- `service.py`：纯业务，可单测  
- **禁止** import 其他 tool 包  
- **同 PR 写测试**：`tools/<id>/tests/` 或 `tests/test_<id>.py`（**iisp-unit-tests**）

### 5. 校验

```bash
./scripts/iisp tool validate tools/<tool-id>/tool.manifest.json
python -m pytest tools/<tool-id>/tests/ -q
```

有 MCP 时调用 `iisp_validate_manifest`。

### 6. 索引（若新场景）

更新 `iisp-catalog/skills-index.yaml`（通常随 Catalog 或主仓 PR）。

### 7. PR

主仓 PR；描述含：意图、tool id、validate 输出。

## Manifest 最小示例

```json
{
  "id": "my-tool",
  "version": "1.0.0",
  "label": "我的工具",
  "contract_version": "v1",
  "runtime": "inprocess",
  "module": "tools.my_tool.invoke:handle",
  "params_schema": {
    "type": "object",
    "properties": {
      "strategy_id": { "type": "string" }
    },
    "required": ["strategy_id"]
  },
  "outputs": ["task_id"],
  "artifacts": []
}
```

## 常见错误

| 错误 | 修复 |
|------|------|
| 在 Gateway 加 if-else 组合 | 改为 Catalog Pipeline |
| tool id 不在 Registry 就被 Pipeline 引用 | 先合并 Tool PR |
| 返回不可 JSON 序列化对象 | 只返回 dict/list/标量 |
