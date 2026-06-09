---
name: iisp-compose-flow
description: Compose Kestra Flow YAML or IISP Pipeline DSL for Catalog. Use when the user wants workflow orchestration, scheduled jobs, combining query/QC/curation/predict tools, or daily automation flows.
---

# IISP — 编排 Flow（Kestra · Vibe Coding）

## 何时使用

用户要：**编排流程**、**定时任务**、**组合查询/质检/归档/预测**、**daily flow**。

## 必读约束

1. 先读 **iisp-vibe-guardrails** 与 [`docs/CODING_STANDARDS.md`](../../../docs/CODING_STANDARDS.md) §5  
2. 阅读 [`docs/IISP_DESIGN_FINAL.md`](../../../docs/IISP_DESIGN_FINAL.md) Part VII、[`docs/TOOLBOX_ORCHESTRATION.md`](../../../docs/TOOLBOX_ORCHESTRATION.md)  
3. **编排统一 Kestra**（Edge + Hub）；**禁止** cron / `iisp flow run` 作为生产方案  
4. **只产出 YAML**，不写 Python 组合逻辑、不改 `workflow_engine`  
5. 每个步骤调用的 `tool_id` **必须**已存在于 Registry

## 工作流（按顺序）

### 1. 获取工具清单

```bash
./scripts/iisp tool list
./scripts/iisp agent context --json   # 规划
```

**不得**编造 tool_id。若无合适 Tool，先走 **iisp-skill-author** / **iisp-create-tool**。

### 2. 澄清

- Flow `id`（snake_case）  
- **Kestra 触发**：Cron / 手动 / Webhook  
- 部署档位：Edge 单机 Kestra 或 Hub  
- 人工卡点（Kestra `Pause` + `ui_url`）  
- 入参 `inputs` / `params_schema`

### 3. 参考范例

- Kestra：[`docs/examples/kestra/daily_ng_curation.yaml`](../../../docs/examples/kestra/daily_ng_curation.yaml)  
- 设计态 DSL：[`iisp-catalog/pipelines/demo/welcome_flow.yaml`](../../../iisp-catalog/pipelines/demo/welcome_flow.yaml)（需编译到 `pipelines/kestra/`）

### 4. 编写 YAML（优先 Kestra 原生）

**运行时权威路径**：`iisp-catalog/pipelines/kestra/<scene>/<flow_id>.yaml`

每步使用 `io.kestra.plugin.core.http.Request` 调 `POST {{ vars.iisp_base }}/v1/tools/{tool_id}/invoke`（见 TOOLBOX_ORCHESTRATION §4.3）。

设计态可先用 Pipeline DSL（`pipelines/<scene>/`），PR 时 **同步或编译** 到 `pipelines/kestra/`。

### 5. 校验

```bash
./scripts/iisp workflow validate iisp-catalog/pipelines/<scene>/<flow_id>.yaml
# Kestra: kestra flow validate …（部署环境）
```

### 6. PR

Catalog PR；更新 `releases.yaml` 若上线。合并后 **Kestra Git sync** 生效。

### 7. 本地验证（非生产）

```bash
./scripts/iisp flow run <flow_id> --param ...   # 仅 dry-run
```

生产定时与历史 **只在 Kestra**。

## 禁止

- cron / systemd 作为主编排  
- Windmill  
- Pipeline 里写 Python、SQL、import  
- 引用未注册 tool  
- 运行时 LLM 决定下一步

## 人工卡点

- Tool 返回 `waiting_human` → Kestra **Pause**  
- 用户在 IISP 完成操作 → `POST /v1/orchestration/resume` 或 Kestra Webhook resume  
- 在 Flow `description` / Catalog `notes` 写清 `ui_url`
