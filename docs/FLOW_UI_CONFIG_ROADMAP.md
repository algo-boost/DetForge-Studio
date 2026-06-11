# Flow 界面配置 — 实施清单

**更新**：2026-06-09 · **关联**：[`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md) · [`TOOLBOX_ORCHESTRATION.md`](./TOOLBOX_ORCHESTRATION.md) · [`UI_REDESIGN_CHECKLIST.md`](./UI_REDESIGN_CHECKLIST.md)

> 目标：在 **不替代 Kestra YAML 权威** 的前提下，让 L2 能在 Shell 内 **触发 Flow、填运行参数、配通知**，减少手改 Git / Kestra UI 的频率。  
> **非目标**：自研 Kestra DAG 编辑器、在 UI 里改 steps 拓扑（仍走 Catalog PR + `iisp-compose-flow`）。

---

## 状态图例

| 标记 | 含义 |
|------|------|
| ⬜ | 未开始 |
| 🚧 | 进行中 |
| ✅ | 已交付 |

---

## 现状（基线）

| 能力 | UI | 后端 |
|------|-----|------|
| 查 Flow 列表 / YAML | ✅ `/flows` | `GET /api/flows/list` |
| 跑 **Legacy** Flow | ✅ FlowCard「运行」 | `POST /api/flows/run` → `flow_runner` |
| 跑 **Kestra** Flow | ❌ `runnable: false` | 仅脚本 `kestra_e2e_smoke.sh` |
| Resume Kestra | ✅ 工作台 / `/flows/runs` | `POST /api/flows/runs/kestra:{id}/resume` |
| 查询策略 | ✅ `/strategies` | strategies JSON / catalog |
| 通知渠道 | ❌ 无表单 | `config.json` → `workflow_notify` |
| 遗留 DAG 编排器 | ⚠️ `/flows/legacy` deprecated | `workflow_engine` |

---

## Phase F1 — Kestra Flow 从 Shell 触发（P0）

**用户价值**：L2 在 `/flows` 选 `daily_ng_curation`，填 `strategy_id` / `time_window`，点「运行」，跳到运行详情。

### 后端

| ID | 任务 | 文件 | 状态 |
|----|------|------|------|
| F1-1 | `kestra_client.execute_flow(namespace, flow_id, inputs)` | `orchestration/kestra_client.py` | ✅ |
| F1-2 | `POST /api/flows/kestra/execute` body: `{ flow_id, namespace?, inputs? }` | `server/routes/tools.py` | ✅ |
| F1-3 | 从 Kestra Flow YAML 解析 `inputs:` → IISP `params_schema` | `orchestration/kestra_inputs.py` | ✅ |
| F1-4 | `list_flow_catalog()`：Kestra 流 `runnable: true`（Kestra 启用时） | `server/services/flows.py` | ✅ |
| F1-5 | 测试：mock Kestra API + `test_kestra_flow_execute.py` | `tests/` | ✅ |

**Kestra API 参考**（与 smoke 脚本一致）：

```http
POST /api/v1/main/executions/iisp/{flow_id}
Content-Type: application/json
{ "strategy_id": "daily_trawl", "time_window": {"preset":"yesterday"} }
```

**inputs → params_schema 映射约定**：

| Kestra input type | UI 控件 |
|-------------------|---------|
| STRING | text / select（见 F2 增强） |
| JSON | textarea 或结构化 time_window 控件 |
| INT / FLOAT | number |
| BOOLEAN | checkbox |

### 前端

| ID | 任务 | 文件 | 状态 |
|----|------|------|------|
| F1-6 | `api.flowKestraExecute({ flow_id, inputs })` | `frontend/src/api/client.js` | ✅ |
| F1-7 | `FlowsCatalogPage`：`onRun` 对 Kestra 走新 API | `pages/FlowsCatalogPage.jsx` | ✅ |
| F1-8 | 成功后跳转 `flowRunPath('kestra:' + execution_id)` | 同上 | ✅ |
| F1-9 | Kestra 未启用时禁用运行 + 提示 | `FlowCard.jsx` | ✅ |

### 验收

```bash
# Kestra + IISP 已启动
curl -s -X POST http://127.0.0.1:5050/api/flows/kestra/execute \
  -H 'Content-Type: application/json' \
  -d '{"flow_id":"daily_ng_curation_smoke","inputs":{}}' | jq
# UI：/flows → daily_ng_curation_smoke → 运行 → /flows/runs/kestra:{id}
pytest tests/test_kestra_flow_execute.py -q
```

---

## Phase F2 — Flow 运行参数增强（P1）

**用户价值**：`strategy_id` 下拉来自已发布策略；`model_id` 来自模型列表（为后续含 predict 的 Flow 做准备）。

| ID | 任务 | 状态 |
|----|------|------|
| F2-1 | Catalog 侧 `flow-ui.schema.yaml` 或扩展 `releases.yaml`：`inputs_ui` 字段类型（`strategy` / `model` / `time_window`） | ⬜ |
| F2-2 | `FlowParamsForm` 按 `inputs_ui` 渲染 StrategySelect / ModelSelect | ⬜ |
| F2-3 | `daily_ng_curation` 的 `inputs_ui` 示例入库 | ⬜ |
| F2-4 | 文档：L2 如何为新 Flow 声明 UI 表单 | ⬜ |

**示例**（`iisp-catalog/pipelines/kestra/daily_ng_curation.ui.json`）：

```json
{
  "flow_id": "daily_ng_curation",
  "inputs_ui": {
    "strategy_id": { "type": "strategy", "label": "捞图策略" },
    "time_window": { "type": "time_window", "label": "时间窗" },
    "reviewer": { "type": "string", "label": "复核人" }
  }
}
```

---

## Phase F3 — 编排通知设置页（P1）

**用户价值**：L2 在 `/config` 配置飞书 / Webhook，无需手改 `config.json`。

| ID | 任务 | 文件 | 状态 |
|----|------|------|------|
| F3-1 | 设置 Tab「编排」或并入 `platform`：`workflow_notify` 表单 | `ConfigPage.jsx` + `settingsUtils.js` | ⬜ |
| F3-2 | 字段：`feishu_webhook_url`、`webhook_url`、`base_url`、email smtp（可选折叠） | 同上 | ⬜ |
| F3-3 | 「发送测试通知」→ `POST /api/forge/workflows/notify-test`（新） | `server/routes/...` | ⬜ |
| F3-4 | 说明文案：仅影响 `notify` Tool / `emit_event` 渠道 | 设置页 | ⬜ |

**已有读取逻辑**：[`studio/forge/workflow_notify.py`](../studio/forge/workflow_notify.py) `_load_notify_config()`。

### 验收

- 保存后 `notify` Tool 能发飞书（配置 webhook 时）
- 未配置时 UI 显示「未配置，仅 UI 渠道落库」

---

## Phase F4 — 组合 Flow 模板（P2）

**用户价值**：一键跑「查询 → 预测 → 再查询 → 出站…」类闭环（YAML 仍 Git 管理，UI 只触发 + 填参）。

| ID | 任务 | 状态 |
|----|------|------|
| F4-1 | 新增 `recall_eval.yaml`（或 `query_predict_curation.yaml`）到 `iisp-catalog/pipelines/kestra/` | ⬜ |
| F4-2 | `inputs`: `strategy_id`, `model_id`, `threshold`, `time_window` | ⬜ |
| F4-3 | steps: query → predict → query(`predict_result`) → curation-* → Pause → notify | ⬜ |
| F4-4 | `inputs_ui` + F1 触发 + F2 模型/策略选择 | ⬜ |
| F4-5 | smoke 变体 + e2e 脚本 | ⬜ |
| F4-6 | `IMPLEMENTATION_ROADMAP` 中 `recall_eval` 标 ✅ | ⬜ |

---

## Phase F5 — 设计态辅助（P3，非阻塞）

| ID | 任务 | 状态 |
|----|------|------|
| F5-1 | `/flows` 增加「从模板新建 Flow」入口 → 打开 Agent 草稿说明 + 链到 `iisp-compose-flow` Skill | ⬜ |
| F5-2 | 校验 YAML：`POST /api/flows/kestra/validate`（解析 + tool_id 注册表检查） | ⬜ |
| F5-3 | 明确废弃 `/flows/legacy` 编排器 Banner + 迁移指南 | ⬜ |

**不做**：Kestra 可视化 step 拖拽编辑（交给 Kestra UI 或 Git）。

---

## 推荐实施顺序

```text
Sprint A（1–2 天）: F1 全条 → Shell 能触发 Kestra smoke + daily_ng
Sprint B（1 天）   : F3 通知设置页
Sprint C（2–3 天） : F2 参数增强 + F4 recall_eval Flow
Sprint D（按需）   : F5 设计态
```

F1 与 F3 可并行（不同文件）。

---

## 文档 / Changelog 同步

每完成一 Phase：

- [ ] [`PLATFORM_CHANGELOG.md`](./PLATFORM_CHANGELOG.md) `[Unreleased]`
- [ ] [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md) 本节状态
- [ ] 若 L1 可见：[`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) §5 组合模块一句

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-09 | 初版：F1–F5 界面可配编排增量清单 |
