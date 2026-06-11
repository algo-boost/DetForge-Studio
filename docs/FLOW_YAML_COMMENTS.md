# Flow YAML 可读性规范（中文注释）

**目的**：以后生成或手改的 Kestra Flow，打开文件就能读懂「谁传给谁」，不必先懂 `fromJson(outputs…)`。

**范例（带全量注释）**：[`iisp-catalog/pipelines/kestra/closed_loop_demo_smoke.yaml`](../iisp-catalog/pipelines/kestra/closed_loop_demo_smoke.yaml)

**Agent 生成**：[`agent/skills/iisp-compose-flow/SKILL.md`](../agent/skills/iisp-compose-flow/SKILL.md) §「中文注释（必写）」

---

## 每个 HTTP 工具步骤必写 4 行注释

写在 `- id: xxx` **上一行**：

```yaml
  # 【步骤 batch】工具 curation-create — 创建筛选批次
  # 入参：task_id ← query.outputs.task_id；reviewer ← Flow.inputs.reviewer
  # 出参：batch_id → export / import / archive
  # 上游包：inputs.upstream = query 整份 outputs
  - id: batch
    type: io.kestra.plugin.core.http.Request
    ...
```

## 表达式对照（给人看）

| YAML 写法 | 人话 |
|-----------|------|
| `inputs.reviewer` | 运行 Flow 时用户填的 reviewer |
| `inputs.row_count` | 运行 Flow 时用户填的 row_count |
| `fromJson(outputs.query.body).outputs.task_id` | 取 **query** 步返回的 task_id |
| `fromJson(outputs.batch.body).outputs.batch_id` | 取 **batch** 步返回的 batch_id |
| `inputs.upstream: {}` | 第一步，没有上游 |
| `inputs.upstream: fromJson(outputs.xxx.body).outputs` | 把 xxx 步整包 outputs 交给本步 |

## 文件头必写

```yaml
# 流程一句话：查询 → 批次 → 导出 → 人工 → 导入 → 归档 → 通知
# 数据接力：task_id → batch_id →（Pause 后按 batch_id 读盘）→ 完成
```

## UI 与 YAML 关系

- Shell **流程图 / 节点详情**：表单展示入参/出参（参数名 + 中文说明 + 配置值/实际值），不再显示 YAML/JSON 原文
- **Git YAML 中文注释**：由后端解析进 `readable` 字段（步骤标题、入参来源、出参去向、上游包）
- Agent 生成 Flow 时**务必写齐** §「每个 HTTP 工具步骤必写 4 行注释」，UI 才能完整可读
- 注释不会从 UI 写回 YAML；维护仍在 Git 中完成
