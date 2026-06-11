---
name: query
description: 查询域统一工具 — execute/preview/task/job/history/strategy。Use when 捞图、查策略、看结果或历史。
---

# 数据查询（query v1.2）

单工具 `query`，通过 `action` 路由；`query-strategy` 为兼容别名。

## action 一览

| action | 说明 |
|--------|------|
| `execute` | 编排/Kestra：按 strategy_id 执行 |
| `run` | 同步 SQL 查询（对应 `POST /api/query`） |
| `preview` | 预览 SQL/筛选，不落地 |
| `task.get` | 按 task_id 取结果元数据 |
| `job.submit` / `job.get` / `job.list` | 异步作业 |
| `history.list` | 查询历史 |
| `strategy.*` | 策略 CRUD + `execute` + `compile_pipeline` |

## REST 薄代理

Legacy 前端仍用 `/api/*`，已由 `tools/query/rest.py` 转发至 dispatch：

| REST | action |
|------|--------|
| `POST /api/query` | `run` |
| `/api/query/jobs*` | `job.*` |
| `GET /api/query/task/:id` | `task.get` |
| `/api/strategies*` | `strategy.*` |

工具状态：`GET /api/query-tool/status`；包装 invoke：`POST /api/query-tool/invoke`。

省略 `action` 且无 `strategy_id` → `strategy.list`。

## execute 参数

| 字段 | 必填 | 说明 |
|------|------|------|
| strategy_id | 是 | 如 `daily_trawl` |
| time_window | 否 | `{"preset":"yesterday"}` |
| data_source | 否 | `detail` 或 `predict_result` |
| env | 否 | 覆盖策略环境变量 |

## 输出

- execute: task_id、row_count、artifacts csv
- strategy.*: strategies / strategy / valid 等

## CLI

```bash
# 策略列表
python3 -m tools.query.cli strategy list

# 执行查询
python3 -m tools.query.cli execute --strategy-id daily_trawl

# stdin JSON（Tool Contract v1）
echo '{"params":{"action":"strategy.list"}}' | python3 -m tools.query.cli

# 平台入口
./scripts/iisp tool invoke query --param action=strategy.list
./scripts/iisp tool run query --param strategy_id=daily_trawl
```

## 集成模式（config.json → query_tool）

| integration | 行为 |
|-------------|------|
| `embedded`（默认） | IISP Shell **直接渲染** Query 页，无 iframe，与 Layout/导航一体 |
| `remote` | Shell iframe 到 `remote_url`（独立部署地址） |
| `standalone` | 本进程仅作说明；实际用 `scripts/query-standalone.sh` |

```json
{
  "query_tool": {
    "integration": "embedded",
    "remote_url": "http://127.0.0.1:6021"
  }
}
```

## 独立部署

```bash
bash scripts/query-standalone.sh
# → http://127.0.0.1:6021/  （UI + REST + /v1/tools/query/invoke）
```

## UI（挂载 /tools/query）

子应用挂载 **`/tools/query`**，Shell 用 iframe 嵌入（`QueryToolEmbed`）。

```bash
bash tools/query/ui/build.sh
# 直接访问 http://127.0.0.1:5050/tools/query/#/query
```

开发：`cd tools/query/ui/frontend && npm run dev`（5174）。

## HTTP

- `POST /v1/tools/query/invoke`
- 独立部署: `python3 tools/query/blueprint/app.py` → `POST /v1/invoke`

## 禁止

- 不要绕过 Gateway 直接写 exports
- 空结果 status=skipped，勿当 failed
