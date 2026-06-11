---
name: query-strategy
description: 已合并入 query；请改用 action=strategy.*
deprecated: true
---

# 查询策略（query-strategy）— 已废弃

**请迁移至 `query` 工具**，使用 `action=strategy.list|get|save|...`。

```bash
./scripts/iisp tool invoke query --param action=strategy.list
python3 -m tools.query.cli strategy list
```

Gateway 兼容：`POST /v1/tools/query-strategy/invoke`（别名，自动映射 action）。
