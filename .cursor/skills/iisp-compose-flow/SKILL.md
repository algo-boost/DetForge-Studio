---
name: iisp-compose-flow
description: Compose an IISP Pipeline YAML from natural language. Use when the user wants workflow orchestration, cron jobs, combining query/QC/curation/predict tools, or daily automation flows.
---

# IISP — 编排 Pipeline（Vibe Coding）

## 何时使用

用户要：**编排流程**、**定时任务**、**组合查询/质检/归档/预测**、**daily flow**。

## 必读约束

1. 先读 **iisp-vibe-guardrails** 与 [`docs/CODING_STANDARDS.md`](../../../docs/CODING_STANDARDS.md) §5  
2. 阅读 [`docs/IISP_DESIGN_FINAL.md`](../../../docs/IISP_DESIGN_FINAL.md) Part VII、Part VIII。  
2. **只产出 YAML**，不写 Python 组合逻辑、不改 `workflow_engine`。  
3. 每个 `nodes[].tool` **必须**已存在于 Registry。

## 工作流（按顺序）

### 1. 获取工具清单

优先 MCP `iisp_list_tools` 或：

```bash
./scripts/iisp agent context --json   # 规划 CLI
./scripts/iisp tool list
```

**不得**编造 tool_id。若无合适 Tool，先走 `iisp-create-tool`  Skill。

### 2. 澄清

- flow `id`（snake_case）  
- 触发方式（Edge cron / Hub Kestra）  
- 人工卡点（哪些步 `waiting_human`，对应 `ui_url`）  
- 入参 `params_schema`

### 3. 参考范例

阅读：`iisp-catalog/pipelines/demo/welcome_flow.yaml`

### 4. 编写 YAML

路径：`iisp-catalog/pipelines/<scene>/<flow_id>.yaml`

```yaml
id: my_flow
label: 人类可读名
version: "1"
description: |
  从用户原话摘要

params_schema:
  type: object
  properties:
    time_window:
      type: object
  required: []

nodes:
  - id: query
    tool: query
    params:
      strategy_id: daily_trawl
      time_window: "{{params.time_window}}"

  - id: export
    tool: curation-export
    params:
      task_id: "{{steps.query.outputs.task_id}}"

notes:
  - 人工上传 COCO：/curation?batch=…，完成后 resume
```

### 5. 模板语法

| 写法 | 含义 |
|------|------|
| `{{params.x}}` | Flow 入参 |
| `{{steps.<node_id>.outputs.<field>}}` | 上游输出 |

### 6. 校验

```bash
./scripts/iisp workflow validate iisp-catalog/pipelines/<scene>/<flow_id>.yaml
```

有 MCP 时调用 `iisp_validate_pipeline`。

### 7. PR

**iisp-catalog** 仓 PR（或主仓内 demo 路径）；更新 `releases.yaml` 若上线。

### 8. 运行验证

```bash
./scripts/iisp flow run <flow_id> --param ...
```

Hub：合并后 Kestra Git sync 或 compile kestra YAML。

## 禁止

- 在 Pipeline 里写 Python、SQL、import  
- 引用未注册 tool  
- 在 Platform DB 存模板替代 YAML  
- 运行时让 LLM 决定下一步（设计态只生成文件）

## 人工卡点

使用会返回 `waiting_human` 的 Tool；在 `notes` 写清：

- `ui_url`（如 `/curation?batch={batch_id}`）  
- Edge：`iisp flow run --resume` 或 API resume  
- Hub：Kestra Pause + `/v1/orchestration/resume`
