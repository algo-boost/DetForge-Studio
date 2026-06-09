# IISP Skill 平台规范（L2 配置者 · Skill-first）

**版本**：v1.1  
**日期**：2026-06-09  
**状态**：定稿 — **L2（SA/算法/光学）** 扩展 Tool 的默认路径  
**读者**：L2 配置者；**L1（交付/客户质检）不参与 Skill 编写**  
**关联**：[`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) §2 · [`DOCS_INDEX.md`](./DOCS_INDEX.md) · [`TOOL_PLUGIN_MODEL.md`](./TOOL_PLUGIN_MODEL.md)

---

## 1. 核心结论

```text
L2 配置者只写 / 只改  SKILL.md（+ 可选一个脚本）
        ↓
平台封装命令  iisp skill pack
        ↓
自动生成：Manifest + invoke + CLI + 默认 UI 描述 + 测试骨架
        ↓
iisp tool validate → PR → Registry 加载
        ↓
完全服从 Tool Contract v1、Catalog Pipeline、Shell UI 规范
```

**专业工程师**只在 Skill 需要「自定义 UI / 复杂 service」时介入；**L1（交付/客户质检）不参与 Skill 编写**。

---

## 2. 两类 Skill（不要混淆）

| 类型 | 位置 | 作用 | 谁写 |
|------|------|------|------|
| **A. 平台 Skill（Platform Skill）** | `skills/<tool_id>/` 或 Tool 包内 `SKILL.md` | 描述**一个可加载工具**的业务契约 | **L2** SA / 算法 / 光学 |
| **B. 创作 Skill（Cursor Skill）** | `.cursor/skills/iisp-skill-author/` 等 | 教 Agent **如何写平台 Skill** | 平台组维护 |

本文 **A** 是交付物；**B** 是开发助手。

---

## 3. 平台 Skill 标准格式（IISP Skill v1）

```markdown
---
name: my-daily-export
description: 按策略导出 CSV。Use when 用户需要按日导出查询结果。
version: "0.1.0"
author: team-qc
tags: [query, export]
ui_level: schema          # schema | wizard | custom（见 §6）
---

# 按日导出

## 何时使用

（业务语言，非专业同学能读懂）

## 输入

- strategy_id: 策略 ID，必填
- time_window: 时间范围 preset，如 yesterday

## 输出

- task_id: 查询任务 ID
- row_count: 行数

## 产物

- csv

## 实现

kind: script
script: scripts/my_export.py
# 或 kind: capability / http（见 §5）

## UI

mode: schema
# wizard 时见 §6.2

## 步骤（给 Agent / 人工实现参考）

1. 调用 platform 查询
2. 写 exports CSV
3. 返回 task_id
```

### 3.1 Frontmatter 字段

| 字段 | 必填 | 说明 |
|------|------|------|
| `name` | ✅ | = Tool `id`，小写连字符 |
| `description` | ✅ | 含 Use when / 何时使用 |
| `version` | 建议 | semver |
| `tags` | 建议 | 工具箱分类 |
| `ui_level` | 建议 | `schema`（默认） |

### 3.2 正文必填节

| 节 | 说明 |
|----|------|
| `## 何时使用` | 业务触发场景 |
| `## 输入` | → `params_schema` |
| `## 输出` | → Manifest `outputs` |
| `## 实现` | script / capability / http |
| `## 步骤` | 自然语言，Agent 生成代码用 |

可选：`## 产物`、`## UI`、`## 注意`

---

## 4. 平台封装：Skill → 可加载 Tool

### 4.1 命令（现有 + 规划）

| 命令 | 状态 | 作用 |
|------|------|------|
| `iisp tool init-from-skill <SKILL.md> --out tools/<id>/` | ✅ 已有 | 生成骨架 |
| `iisp skill validate <SKILL.md>` | 规划 | 只验 Skill 格式 |
| `iisp skill pack <SKILL.md> [--out tools/<id>/]` | 规划 | validate + init + 按 `## 实现` 注入适配器 |
| `iisp skill pack --install` | 规划 | pack 后注册到本地 Registry |

**封装器职责（平台代码，只写一次）**：

1. 解析 Skill v1 → JSON Schema + Manifest  
2. 生成 **invoke.py / cli.py**（薄包装，不调业务 if-else）  
3. 按 `kind` 生成 **script 适配器** 或 Capability 壳  
4. 生成 **ui.manifest.json**（UI 描述，见 §6）  
5. 运行 **validate**，输出人类可读错误（中文）  

### 4.2 实现 kind 三种模式（非专业优先 script）

| kind | 非专业作者做什么 | 平台生成什么 |
|------|------------------|--------------|
| **script** | 只写/改一个 `.py` 脚本，读 env JSON、print JSON | `script_runner.py` 包装 stdin/stdout |
| **capability** | 在 Agent 帮助下填 `service.py` 的 TODO | 标准 Tool 包 |
| **http** | 只提供 Blueprint URL | Manifest `runtime: http` |

**script 模式约定**（最简单）：

```python
# scripts/my_export.py — 业务同学只需改 main 里逻辑
import json, sys
from skill_sdk import load_params, ok, fail  # 平台提供 lib/iisp-skill-sdk

def main(params, inputs):
    strategy_id = params["strategy_id"]
    # ... 业务逻辑 ...
    return ok(task_id="abc", row_count=100)

if __name__ == "__main__":
    main(load_params())
```

平台 `skill pack` 自动包一层 CLI/Manifest，**作者不必懂 Flask/Gateway**。

---

## 5. 完全服从平台协议

封装后的 Tool **强制**：

| 协议 | 服从方式 |
|------|----------|
| Tool Contract v1 | 自动生成 invoke/cli，status 枚举固定 |
| Manifest | `contract_version: v1`，禁止 hand-edit 绕过 validate |
| 编排 | 只出现在 Catalog YAML 的 `tool:` 字段 |
| 跨模块 | 只传 JSON/URI；script 内可调 `iisp-sdk` 调其他 tool |
| 安全 | 无密钥进 Skill；用 config/env |
| UI | 见 §6，默认 **schema 表单**，不强制写 React |

**禁止**：Skill 里写「直接改 workflow_engine」；封装器 CI 拒绝。

---

## 6. UI 构建方式（非专业默认）

**原则**：没有特殊需求 **不写 React**；Shell 统一渲染。

| ui_level | 谁适合 | Shell 行为 |
|----------|--------|------------|
| **schema**（默认） | 绝大多数 | 工具箱 + RJSF 读 `params_schema` |
| **wizard** | 多步表单 | 读 Skill `## UI` 的步骤定义 → 向导页 |
| **custom** | 复杂交互 | Tool 包 `ui/`（专业同事或 Agent 生成） |

### 6.1 schema（默认）

Skill 只需写好 `## 输入`；pack 生成 JSON Schema。  
用户在 **工具箱** 填表 → `POST /v1/tools/{id}/invoke`。

### 6.2 wizard（Skill 声明）

```markdown
## UI

mode: wizard
steps:
  - id: pick_strategy
    fields: [strategy_id]
  - id: pick_time
    fields: [time_window]
  - id: confirm
    summary: true
```

Shell 读 `ui.manifest.json`（pack 生成）渲染向导。

### 6.3 custom

```markdown
## UI

mode: custom
mount: /tools/my-daily-export
```

需 Tool 包内 `ui/`，遵守 [`CODING_STANDARDS.md`](./CODING_STANDARDS.md) §6；**非默认路径**。

### 6.4 与独立 UI 的关系

- **嵌入**：`/tools/<id>` 挂载  
- **独立**：viz 类 submodule 端口；Skill 里 `standalone_port: 6010`  
- 非专业：**不选 custom** 即可

---

## 7. L2 配置者工作流（Skill → Tool → Kestra）

```mermaid
flowchart LR
  A[业务描述需求] --> B[Cursor + iisp-skill-author]
  B --> C[skills/id/SKILL.md]
  C --> D[可选: 改 script.py]
  D --> E[iisp skill pack]
  E --> F[iisp tool validate]
  F --> G[PR]
  G --> H[工具箱可见]
  H --> I[iisp-compose-flow 编排]
```

| 步骤 | 工具 | 说明 |
|------|------|------|
| 1 | 对话 / 文档 | 说清输入输出 |
| 2 | **iisp-skill-author** | Agent 写 Skill v1 |
| 3 | 改脚本 | 仅 `kind: script` 时 |
| 4 | **iisp skill pack** | 平台封装 |
| 5 | **iisp-skill-pack** Skill | Agent 自检 + validate |
| 6 | PR | 业务负责人 approve |
| 7 | **iisp-compose-flow** | 如需进流水线 |

**不需要**：学 React、学 Kestra YAML 语法（Agent 代写 Pipeline）、改 Platform 代码。

---

## 8. 平台提供的「封装 Skill」（Cursor）

| Cursor Skill | 用户说 | 作用 |
|--------------|--------|------|
| **iisp-skill-author** | 「做一个导出工具」 | 只产出/改 **平台 Skill v1** |
| **iisp-skill-pack** | 「打包成平台工具」 | 跑 pack + validate + 解释错误 |
| **iisp-compose-flow** | 「每天跑一下」 | 产出 Pipeline YAML |
| **iisp-create-tool** | 工程兜底 | 完整 Tool 包（专业） |

索引： [`.cursor/skills/README.md`](../.cursor/skills/README.md)

---

## 9. 加载与发现

```text
skills/<id>/SKILL.md          # 源（Git）
        ↓ pack
tools/<id>/tool.manifest.json # 注册
        ↓
Registry + 工具箱 + MCP list_tools
        ↓
iisp-catalog/skills-index.yaml  # 人类索引（label、贡献者）
```

**热加载（规划）**：`iisp skill pack --install` 开发环境即时可见。

---

## 10. 与 `.iisp-skill` 分发包（规划）

```text
my-export.iisp-skill/
├── SKILL.md
├── scripts/my_export.py
└── skill.lock.json           # pack 元数据、platform 版本
```

内网分发：上传 → `iisp skill install my-export.iisp-skill` → 同 pack 流程。

---

## 11. 质量门禁（非专业友好）

| 检查 | 错误提示语言 |
|------|--------------|
| `iisp skill validate` | 中文：缺 `## 输入`、name 非法 |
| `iisp tool validate` | 中文：outputs 与 Skill 不一致 |
| CI | 无 validate 不过 merge |
| 人工 | CODEOWNERS 业务负责人 |

---

## 12. 平台一次性建设（Skill 路线依赖）

| 项 | 说明 |
|----|------|
| `lib/iisp-skill-sdk` | script 模式 `load_params` / `ok()` / `fail()` |
| `iisp skill pack` | 封装器 CLI |
| Shell RJSF 工具箱 | schema UI |
| Shell wizard 渲染 | 读 ui.manifest.json |
| Skill v1 解析器 | 扩展 `skill_parser.py` |
| 中文 validate 消息 | 非专业可读 |

**不做**：每个 Tool 单独写 Flask 路由。

---

## 13. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.1 | 2026-06-09 | 读者改为 L2；对齐 Kestra、DOCS_INDEX |
| v1.0 | 2026-06-09 | Skill-first、UI 三级、封装命令 |
