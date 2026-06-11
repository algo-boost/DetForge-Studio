# 编排闭环演示指南

两种 Flow，覆盖 **有/无业务库** 场景，步骤一致：

```text
查询 → 返回 task_id/result.csv → 创建批次 → 导出出站包
  → 人工 Pause → 导入 COCO → 归档 → 通知
```

| Flow id | 查询方式 | 适用 |
|---------|----------|------|
| **`closed_loop_demo_smoke`** | `smoke-query` 写样本 CSV | **推荐演示**，无需数据库 |
| **`closed_loop_demo`** | `query` 工具查业务库 | 生产策略 `daily_trawl` 等 |

---

## 一键全自动（推荐）

```bash
cd tools/DetForge-Studio
bash scripts/run-closed-loop-demo.sh
```

脚本会：导入 Flow → 触发 Kestra → 等 Pause → 从 batch 步骤输出解析 batch_id → 自动回传 COCO → Resume → 直到 **SUCCESS**。

若 Kestra 导入 Flow 超时或 OOM，先执行 `docker restart deploy-kestra-1` 再重试。

---

## 方式二：Shell UI 手动体验

1. 打开 http://127.0.0.1:5173/flows（L2 配置模式）
2. 选 **`closed_loop_demo_smoke`**（或 `closed_loop_demo` 填策略/时间窗）
3. 点 **运行** → 进入运行详情
4. 状态 **PAUSED** 时：
   - 记下 `batch_id`
   - 打开 http://127.0.0.1:5173/curation?batch_id=…
   - 确认/上传筛选 COCO
5. 在运行详情或工作台点 **Resume**
6. 完成后可在 `/query-results?task=…` 查看查询结果（真实库模式）

仅触发、不自动 Resume：

```bash
bash scripts/run-closed-loop-demo.sh --real --ui
```

---

## 方式三：API

```bash
# 样本模式
curl -s -X POST http://127.0.0.1:5050/api/flows/kestra/execute \
  -H 'Content-Type: application/json' \
  -d '{"flow_id":"closed_loop_demo_smoke","inputs":{"reviewer":"me"}}' | jq

# 真实库
curl -s -X POST http://127.0.0.1:5050/api/flows/kestra/execute \
  -H 'Content-Type: application/json' \
  -d '{
    "flow_id": "closed_loop_demo",
    "inputs": {
      "strategy_id": "daily_trawl",
      "time_window": {"preset": "yesterday"},
      "reviewer": "demo"
    }
  }' | jq
```

---

## 前置条件

- `bash deploy/scripts/platform-start.sh`（IISP 5050 + Kestra 8080）
- 前端：`cd frontend && npm run dev`（5173）
- 样本模式：`POST /api/forge/schema/init`（脚本已调用）
- 真实库模式：`config.json` 中数据库可读，且时间窗内有数据

---

## 相关文件

- Flow YAML：`iisp-catalog/pipelines/kestra/closed_loop_demo*.yaml`
- 脚本：`scripts/run-closed-loop-demo.sh`
- 迷你演示（无 Kestra）：http://127.0.0.1:5173/flows/demo
