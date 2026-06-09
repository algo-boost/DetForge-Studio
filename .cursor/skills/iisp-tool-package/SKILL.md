---
name: iisp-tool-package
description: >-
  Scaffolds or edits a standard IISP Tool Package with CLI, invoke, service,
  manifest, tests, and SKILL. Use when creating tools, packages, CLI entrypoints,
  standalone UI, blueprint HTTP service, or migrating studio modules to tools/.
---

# IISP 标准工具包

规范：[`docs/TOOL_PLUGIN_MODEL.md`](../../docs/TOOL_PLUGIN_MODEL.md)

## 每个 Tool 必须交付

| 产物 | 路径 |
|------|------|
| Manifest | `tool.manifest.json` |
| 业务 | `service.py` |
| Gateway | `invoke.py` → 只调 service |
| **CLI** | `cli.py` — stdin/stdout **与 invoke 同构 JSON** |
| **Skill** | `skills/SKILL.md` 或 `skills/<id>/SKILL.md` |
| 测试 | `tests/test_invoke.py` + CLI golden JSON |
| 文档 | `README.md` — 含 CLI 一行示例 |

## 可选

| 产物 | 路径 |
|------|------|
| 独立 HTTP | `blueprint/app.py` — `POST /v1/invoke` |
| 独立/嵌入 UI | `ui/` — Shell 挂载 `/tools/<id>` |
| pip 包 | `pyproject.toml` |

## CLI 规范

**stdin**：

```json
{"run_id":"local","step_id":"main","params":{},"inputs":{"upstream":{}}}
```

**stdout**（单行）：

```json
{"status":"done","outputs":{},"artifacts":[]}
```

实现可复用 `lib/iisp-cli`（规划）或复制 `tools/_template/cli.py`。

## Scaffold

```bash
./scripts/iisp tool init-from-skill skills/<scene>/SKILL.md --out tools/<id>
# 然后补全 cli.py、tests/test_cli_golden.json
```

## 依赖

- 可依赖：`lib/platform`、`lib/iisp-contract`、领域 lib（`coco-io` 等）
- **禁止**：import 其他 Tool 的 `service.py`

## Manifest runtime

| 场景 | runtime |
|------|---------|
| Edge 默认 | `inprocess` + `cli` 字段 |
| GPU/重/独立团队 | `http` + blueprint |
| 仅脚本 | `cli` only（Registry kind=cli） |

## 独立运行

```bash
# CLI
echo '{"params":{"key":"val"}}' | python -m tools.<id>.cli

# Blueprint（若有）
python tools/<id>/blueprint/app.py

# 经平台
curl -X POST http://127.0.0.1:5050/v1/tools/<id>/invoke -H 'Content-Type: application/json' -d '{"params":{}}'
```

## UI

- 复杂 UI → `ui/` 子应用；简单 → 仅 Shell 工具箱 + RJSF params 表单
- UI **只**调 invoke API，不 import 其他 Tool

## 完成后

```bash
./scripts/iisp tool validate tools/<id>/tool.manifest.json
python -m pytest tools/<id>/tests/ -q
```

更新 `iisp-catalog/skills-index.yaml`（新场景时）。

## 禁止

- 在 Platform Core 加业务逻辑
- 无 CLI 的「半套 Tool」（除非纯 HTTP blueprint 且文档说明）
- 无 Skill 的 Tool PR
