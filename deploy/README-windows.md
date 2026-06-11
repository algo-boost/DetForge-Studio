# IISP 一体化原生部署（Windows，无 Docker）

Windows 原生路径：IISP + Kestra 同机运行，**共用现有 MySQL 实例**。
与 [`README-native.md`](./README-native.md)（macOS/Linux）共用同一套 `iisp deploy` 编排逻辑，
仅启动入口换成 PowerShell 薄脚本，Kestra 改为 `java -jar` 运行。

> Linux 的 `deploy/vendor/kestra` 是平台原生可执行文件，**Windows 不可直接运行**。
> Windows 改用同版本 uber-jar `deploy/vendor/kestra.jar`（`iisp deploy fetch` 自动下载），
> 通过 `java -jar` 启动；`io.kestra.plugin.core`（含 http.Request / log.Log / flow.*）已内置于该 jar。

---

## 前置要求

| 项 | 要求 |
|----|------|
| Java | **21+**，加入 PATH（推荐 [Temurin 21](https://adoptium.net/)，安装时勾选 *Add to PATH*） |
| Python | 3.10+，已 `pip install -r requirements.txt` |
| Node | 构建前端用（`npm ci && npm run build`） |
| MySQL | 与 IISP 相同连接（`config.json` 的 `db_host`/`db_port`/`db_user`/`db_password`） |
| 内存 | 建议 ≥8GB（Kestra `-Xmx4096m`） |

验证 Java：

```powershell
java -version   # 需显示 21+
```

`config.json` 与 `.config.key` **不入库**，需自行放置到 DetForge-Studio 根目录。

---

## 一键启动

在 DetForge-Studio 根目录的 **PowerShell** 中：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\scripts\platform-start.ps1
```

首次会自动：

1. 下载 Kestra（版本见 `deploy/native/env.defaults`）到 `deploy\vendor\kestra.jar`
2. `CREATE DATABASE IF NOT EXISTS kestra`
3. 从 `config.json` 渲染 `deploy\runtime\kestra-application.yml`（路径自动转正斜杠）
4. 后台启动 Kestra（`java -jar`）→ 再启动 IISP（`python app.py`）

| 服务 | 地址 |
|------|------|
| IISP 工作台 | http://127.0.0.1:5050/ |
| Kestra UI | http://127.0.0.1:8080/（`admin@kestra.io` / `Admin1234`） |

```powershell
powershell -File deploy\scripts\platform-status.ps1   # 状态
powershell -File deploy\scripts\platform-stop.ps1      # 停止（taskkill /T 连同 JVM 子进程）
```

日志：`deploy\runtime\iisp.log`、`deploy\runtime\kestra.log`

> 若 PowerShell 提示脚本被禁止运行，使用上面的 `-ExecutionPolicy Bypass`，
> 或当前会话执行一次 `Set-ExecutionPolicy -Scope Process Bypass`。

---

## 也可直接用 CLI（跨平台一致）

PowerShell 脚本只是薄封装，等价于：

```powershell
python -m cli.main deploy fetch          # 仅下载 Kestra 资产
python -m cli.main deploy bootstrap-db   # 建 kestra 库
python -m cli.main deploy render-config  # 渲染配置
python -m cli.main deploy start          # 启动 Kestra + IISP
python -m cli.main deploy status         # 状态
python -m cli.main deploy stop           # 停止
```

---

## 离线安装包（从 macOS/Linux 打包带到 Windows）

`platform-pack.sh` 打出的 tar.gz 含 Linux 版 `vendor/kestra`，在 Windows **不可用**，
但其余内容（代码、`vendor/plugins/`、前端构建产物）可复用：

1. 目标 Windows 机解压安装包
2. 放置 `config.json`、`.config.key`
3. `python -m venv .venv` → `.\.venv\Scripts\Activate.ps1` → `pip install -r requirements.txt`
4. 前端（若包内未含 dist）：`cd frontend; npm ci; npm run build; cd ..`
5. 启动：`powershell -File deploy\scripts\platform-start.ps1`
   - 首次启动检测到没有 `kestra.jar`，会自动 `deploy fetch` 下载（**需联网一次**）

> 完全离线场景：在有网的 Windows 机先跑一次 `python -m cli.main deploy fetch`，
> 把生成的 `deploy\vendor\kestra.jar` 一并拷入目标机即可免联网启动。

---

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `KESTRA_VERSION` | 见 `native/env.defaults` | 下载的 Kestra 版本 |
| `KESTRA_PORT` | `8080` | Kestra HTTP |
| `IISP_PORT` | `5050` | Flask（app.py 固定 5050） |
| `ENV_IISP_BASE` | `http://127.0.0.1:5050` | Flow 内 `{{ envs.iisp_base }}` |
| `KESTRA_MYSQL_DATABASE` | `kestra` | 编排库名 |
| `JAVA_OPTS` | `-Xms512m -Xmx4096m ...` | JVM 参数 |

PowerShell 设置示例：`$env:KESTRA_PORT = '8081'`，再执行 start。

---

## 故障排查

- **`未找到 Python`**：确保 `python` / `py` 在 PATH（安装 Python 时勾选 *Add to PATH*）
- **`需要 Java 21+`**：`java -version` 不到 21，或 java 不在 PATH（装 Temurin 21 并重开终端）
- **Kestra 启动超时**：看 `deploy\runtime\kestra.log`；确认 MySQL 可达、`kestra` 库已建
- **脚本无法运行（ExecutionPolicy）**：用 `powershell -ExecutionPolicy Bypass -File ...`
- **端口占用**：`netstat -ano | findstr 8080` 查 PID，`taskkill /PID <pid> /F`
- **下载失败**：手动 `python -m cli.main deploy fetch`，或在有网机下载 `kestra.jar` 后拷入 `deploy\vendor\`

---

## 与其它部署路径对比

| | Windows 原生（本文） | macOS/Linux 原生 | Docker Compose |
|--|---------------------|------------------|----------------|
| 启动入口 | `platform-start.ps1` | `platform-start.sh` | `docker compose up` |
| Kestra | `java -jar vendor\kestra.jar` | `vendor/kestra` 可执行 | 容器镜像 |
| 数据库 | MySQL 同实例 `kestra` 库 | MySQL 同实例 `kestra` 库 | 内置 Postgres |
| 适用 | 内网 Windows 单机 | 内网 Unix 单机 | 本机快速试用 |
