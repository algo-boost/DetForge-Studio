# 部署方式

IISP 编排栈有两种等价路径，**生产/内网推荐原生一体化**（无需 Docker）：

| 方式 | 文档 | 说明 |
|------|------|------|
| **原生打包** | [`README-native.md`](./README-native.md) | IISP + Kestra JAR + 共用 MySQL；`platform-start.sh` / `platform-pack.sh` |
| Docker Compose | 下文 | 本地开发；内置 Postgres |

---

# Kestra 本地开发（Docker）

与 [`docs/IMPLEMENTATION_ROADMAP.md`](../docs/IMPLEMENTATION_ROADMAP.md) 对齐。

## 前置

1. **IISP 主服务**在本机 `:5050` 运行（Kestra 通过 `host.docker.internal` 调用 `/v1/tools/*/invoke`）
2. **Docker**：macOS 推荐 Colima（`brew install colima docker docker-compose`），建议 **≥8GB 内存**
3. Colima 启动：`colima start --memory 8 --cpu 4`

## 启动

```bash
cd deploy
docker-compose -f docker-compose.kestra.yml up -d
```

- Kestra UI：<http://localhost:8080>（`admin@kestra.io` / `Admin1234`）
- 端到端冒烟：`bash deploy/scripts/kestra_e2e_smoke.sh`
- Pause/Resume 冒烟：`bash deploy/scripts/kestra_pause_resume_smoke.sh`
- **M2-run 全链路**（Pause → COCO 回传 → Resume → SUCCESS）：`bash deploy/scripts/daily_ng_pause_resume_e2e.sh`

## 验证 daily_ng_curation

1. 确认 Gateway：

```bash
curl -s http://127.0.0.1:5050/v1/tools | head
curl -s -X POST http://127.0.0.1:5050/v1/tools/query/invoke \
  -H 'Content-Type: application/json' \
  -d '{"run_id":"smoke","step_id":"query","params":{"strategy_id":"daily_trawl","time_window":{"preset":"yesterday"},"data_source":"detail"},"inputs":{"upstream":{}}}'
```

2. 在 Kestra UI 打开 Flow **`iisp.daily_ng_curation`**，手动 Execute
3. 在 `human_edit` Pause 步骤：到 IISP 工作台 `/` 完成 COCO 编辑后 Resume

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `ENV_IISP_BASE` | `http://host.docker.internal:5050` | Kestra 容器内调用 IISP |
| Kestra 登录 | `admin@kestra.io` / `Admin1234` | compose 内 basic-auth |

## 停止

```bash
docker compose -f docker-compose.kestra.yml down
```

## 原生一键启动（无 Docker）

```bash
bash deploy/scripts/platform-start.sh
```

详见 [`README-native.md`](./README-native.md)。
