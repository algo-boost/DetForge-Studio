# Skills → Tool 共建规范

> **主文档已升级**：非专业开发者请读 **[`SKILL_PLATFORM.md`](./SKILL_PLATFORM.md)**（Skill-first、封装命令、UI 三级）。  
> 本文保留 **init-from-skill 命令细节** 与 **L1–L4 贡献流程**。

## 目标

将 **Platform Skill（SKILL.md）** 转化为可注册进 IISP 工具箱的 `tool.manifest.json` + 运行入口（CLI / script / capability）。

## 推荐路径（非专业）

```text
Cursor + iisp-skill-author  →  skills/<id>/SKILL.md
Cursor + iisp-skill-pack    →  tools/<id>/  + validate
PR
```

详见 [`SKILL_PLATFORM.md`](./SKILL_PLATFORM.md) §7。

## SKILL.md 必填结构（IISP Skill v1 摘要）

```markdown
---
name: my-scenario-tool
description: 一句话能力说明。Use when 触发场景描述。
ui_level: schema
---

# 技能标题

## 何时使用
…

## 输入
- param_a: 说明

## 输出
- result_id

## 实现
kind: script
script: scripts/my_script.py
```

完整格式见 [`SKILL_PLATFORM.md`](./SKILL_PLATFORM.md) §3。

## 转化命令

```bash
./scripts/iisp tool init-from-skill skills/my-scenario/SKILL.md --out tools/my_tool
# 规划：./scripts/iisp skill pack skills/my-scenario/SKILL.md --out tools/my_tool
```

生成文件：

- `tool.manifest.json`
- `capability.py` 或 script 适配器（按 `## 实现` kind）
- `cli.py`（stdin/stdout JSON）
- `tests/test_capability.py`
- `SKILL.md` 副本

## 贡献流程

1. **L1** 沉淀 `skills/<scene>/SKILL.md`（**iisp-skill-author**）
2. **L2** `init-from-skill` / **skill pack**，实现 script 或 service，提交主仓 PR（**iisp-skill-pack**）
3. CI：`iisp tool validate`
4. **L3** Catalog Pipeline 引用 `tool: <id>`（**iisp-compose-flow**）
5. **L4** 部署侧 `iisp catalog sync`

## 示范

- Skill：[`skills/yf-door-panel-query/SKILL.md`](../skills/yf-door-panel-query/SKILL.md)
- 工具包：[`packages/yf_door_panel_query/`](../packages/yf_door_panel_query/)
- Catalog 索引：[`iisp-catalog/skills-index.yaml`](../iisp-catalog/skills-index.yaml)

## 检查清单

- [ ] `name` 与 Manifest `id` 一致
- [ ] `## 输出` 与 Manifest `outputs` 一致
- [ ] 编排参数与 `params_schema` 一致
- [ ] `iisp tool validate` 通过
- [ ] 非 schema UI 需 CODEOWNERS 前端审批
- [ ] Catalog PR 已更新（若影响策略/流水线）
