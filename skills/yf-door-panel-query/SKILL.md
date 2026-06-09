---
name: yf-door-panel-query
description: 延锋门板平台数据查询。Use when 需要按策略从 vision_backend 捞取 NG/缺陷样本并创建查询任务。
---

# 延锋门板查询

## 输入

- strategy_id: 查询策略 ID（如 daily_trawl）
- time_window: 时间窗口 preset 或起止时间
- data_source: detail 或 predict_result

## 输出

- task_id: 查询任务 ID
- row_count: 命中行数
- count: 同 row_count

## CLI

```bash
python -m studio.query.cli run
```

## 实现

`studio.query.capabilities:QueryCapability`
