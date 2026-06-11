# IISP 一体化原生部署（无 Docker）

**推荐生产/内网路径**：IISP + Kestra 同机运行，**共用现有 MySQL 实例**（`vision_backend` 读库 + `detforge` 写库 + 独立 `kestra` 库）。

Docker Compose 仍可用于本地开发，见 [`README.md`](./README.md)。

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│  同一台机器 / 同一安装包                                    │
│  ┌──────────────┐    HTTP     ┌──────────────────────┐  │
│  │ IISP :5050   │◄───────────│ Kestra :8080          │  │
│  │ app.py       │  /v1/tools │ vendor/kestra + plugins│  │
│  └──────┬───────┘            └──────────┬─────────────┘  │
│         │                               │                 │
│         └───────────┬───────────────────┘                 │
│                     ▼                                     │
│              MySQL（config.json）                          │
│    vision_backend │ detforge │ kestra（Flyway 自动建表）    │
└─────────────────────────────────────────────────────────┘
```

Flow 权威目录：`iisp-catalog/pipelines/kestra/`（Kestra 文件监听热加载）。

---

## 代码分层（解耦）

部署逻辑**不在 shell 里堆业务**，按职责拆分：

| 层 | 路径 | 职责 |
|----|------|------|
| **制品 / 模板** | `deploy/native/`、`deploy/docker-compose*.yml` | env 默认值、Kestra YAML 模板 |
| **编排域** | `orchestration/native/` | MySQL 设置、库引导、配置渲染、进程管理 |
| **CLI 入口** | `cli/deploy_cmds.py` → `iisp deploy *` | 子命令编排 |
| **薄脚本** | `deploy/scripts/platform-*.sh` | 一行转调 `python -m cli.main deploy …` |
| **运行时 API** | `orchestration/kestra_client.py` | 已运行 Kestra 的 Resume / 查询（与部署解耦） |

```bash
python -m cli.main deploy bootstrap-db
python -m cli.main deploy render-config
python -m cli.main deploy start | stop | status
```

---

| 项 | 要求 |
|----|------|
| Java | **21+**（`brew install openjdk@21`） |
| Python | 3.10+，已 `pip install -r requirements.txt` |
| MySQL | 与 IISP 相同连接（`config.json` 的 `db_host` / `db_user` / `db_password`） |
| 内存 | 建议 ≥8GB（Kestra `-Xmx4096m`） |

`config.json` 与 `.config.key` **不入库**；目标机需自行放置。

可选配置项（默认即可）：

```json
{
  "kestra_database": "kestra"
}
```

---

## 一键启动

```bash
# 在 DetForge-Studio 根目录
bash deploy/scripts/platform-start.sh
```

首次会自动：

1. 下载 Kestra 1.3.21 到 `deploy/vendor/`（优先从 Docker 镜像提取含插件；无 Docker 则走 API + 插件安装）
2. `CREATE DATABASE IF NOT EXISTS kestra`
3. 从 `config.json` 渲染 `deploy/runtime/kestra-application.yml`
4. 后台启动 Kestra → 再启动 IISP

| 服务 | 地址 |
|------|------|
| IISP 工作台 | http://127.0.0.1:5050/ |
| Kestra UI | http://127.0.0.1:8080/（`admin@kestra.io` / `Admin1234`） |

```bash
bash deploy/scripts/platform-status.sh   # 状态
bash deploy/scripts/platform-stop.sh     # 停止
```

日志：`deploy/runtime/iisp.log`、`deploy/runtime/kestra.log`

---

## 冒烟

```bash
bash deploy/scripts/kestra_e2e_smoke.sh
bash deploy/scripts/kestra_pause_resume_smoke.sh
```

---

## 打包分发

在有 Docker 的机器上执行（确保 vendor 含完整插件）：

```bash
bash deploy/scripts/platform-pack.sh
# → packaging/dist/iisp-platform-1.3.21-YYYYMMDD.tar.gz
```

目标机：

```bash
tar xzf iisp-platform-*.tar.gz && cd iisp-platform-*
cp /path/to/config.json . && cp /path/to/.config.key .
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
bash deploy/scripts/platform-start.sh
```

安装包已包含 `deploy/vendor/kestra` 与 `plugins/`，**目标机无需 Docker**。

---

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `KESTRA_PORT` | `8080` | Kestra HTTP |
| `IISP_PORT` | `5050` | Flask（app.py 固定 5050，改端口需改 app.py） |
| `ENV_IISP_BASE` | `http://127.0.0.1:5050` | Flow 内 Pebble `{{ envs.iisp_base }}` |
| `KESTRA_MYSQL_DATABASE` | `kestra` | 编排库名（勿与 `detforge` 混用） |
| `KESTRA_USER` / `KESTRA_PASSWORD` | 见 `native/env.defaults` | Basic Auth |

修改默认值：编辑 `deploy/native/env.defaults` 或 export 后执行 `platform-start.sh`。

---

## 与 Docker 路径对比

| | 原生（本文） | Docker Compose |
|--|-------------|----------------|
| 数据库 | **MySQL** 同实例 `kestra` 库 | 内置 Postgres |
| Kestra 二进制 | `deploy/vendor/` | 容器镜像 |
| IISP 调用地址 | `127.0.0.1:5050` | `host.docker.internal:5050` |
| 适用 | 内网单机、离线安装包 | 本机快速试用 |

---

## systemd（可选）

```ini
[Unit]
Description=IISP Platform (Kestra + IISP)
After=network-online.target mysql.service

[Service]
Type=forking
WorkingDirectory=/opt/iisp-platform
ExecStart=/opt/iisp-platform/deploy/scripts/platform-start.sh
ExecStop=/opt/iisp-platform/deploy/scripts/platform-stop.sh
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

---

## 故障排查

- **Kestra 启动超时**：查看 `deploy/runtime/kestra.log`；确认 Java 21、MySQL 可达、库已创建
- **Flow HTTP 失败**：确认 `ENV_IISP_BASE` 与 IISP 端口一致
- **插件缺失**：重新执行 `bash deploy/scripts/fetch_kestra.sh`（建议在有 Docker 的环境打包）
