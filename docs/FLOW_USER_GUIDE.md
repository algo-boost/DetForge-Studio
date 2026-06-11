# 编排怎么用（使用者视角）

**一句话**：日常在 Shell **选任务、填参数、点运行**；要改流程结构时 **改 Git YAML**（或让 Agent 生成），不是拖拽画 DAG。

---

## 两类人、两件事

| 角色 | 做什么 | 去哪 |
|------|--------|------|
| **运行者（L1/L2）** | 选已有编排任务、填策略/时间窗、运行、人工 Resume | `/flows` |
| **设计者（L2）** | 新增/调整步骤顺序、工具接线、定时 Cron | Git `iisp-catalog/pipelines/kestra/*.yaml` 或 Cursor + `iisp-compose-flow` |

**当前设计故意不做**：在网页里拖拽改拓扑（那是 Kestra 英文 UI 或 Git 的事）。

---

## 运行者：5 步跑通

1. 侧栏 **流水线 → 编排**（`/flows`）
2. **编排任务** 表里看流程图，点 **详情** 或 **运行**
3. 在任务详情填 `strategy_id`、`time_window`、`reviewer` 等 → **立即运行**
4. **执行历史** Tab 或运行详情里看状态；`待人工` 时去 **筛选归档** 改 COCO
5. 回到运行详情点 **继续运行**（Resume）

推荐入门任务：`closed_loop_demo_smoke`（无需数据库）。

---

## 设计者：如何「编排」新流程

### 方式 A：复制改（最常见）

1. 复制范例：`closed_loop_demo_smoke.yaml` 或 `daily_ng_curation.yaml`
2. 改 `id`、各步 `tool` URI、`params` 里的接线（注释已标 `←` `→`）
3. 保存到 `iisp-catalog/pipelines/kestra/`
4. 同步 Catalog → `/flows` 刷新可见
5. 注释规范：[`FLOW_YAML_COMMENTS.md`](./FLOW_YAML_COMMENTS.md)

### 方式 B：Agent 生成

对 Cursor 说：「按 iisp-compose-flow 生成 xxx 流程」，产出带中文注释的 YAML → 同上入库。

### 方式 C：Kestra UI（可选）

`/flows/kestra` 嵌入英文编辑器，适合熟 Kestra 的人；**权威源仍是 Git YAML**。

---

## 三张图记住分工

```text
┌─────────────┐     只读看图      ┌─────────────┐
│  /flows UI  │ ───────────────► │ 理解步骤/契约 │
└─────────────┘                   └─────────────┘

┌─────────────┐     编辑接线      ┌─────────────┐
│  Git YAML   │ ───────────────► │ 定义谁传给谁  │
└─────────────┘                   └─────────────┘

┌─────────────┐     执行调度      ┌─────────────┐
│   Kestra    │ ───────────────► │ 定时/重试/历史 │
└─────────────┘                   └─────────────┘
```

---

## 相关文档

- YAML 注释规范：[`FLOW_YAML_COMMENTS.md`](./FLOW_YAML_COMMENTS.md)
- 闭环演示：[`examples/CLOSED_LOOP_DEMO.md`](./examples/CLOSED_LOOP_DEMO.md)
- 工具契约：[`TOOLBOX_ORCHESTRATION.md`](./TOOLBOX_ORCHESTRATION.md)
