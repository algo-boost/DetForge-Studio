# 配置文件说明

## 文件位置

| 文件 | 说明 |
|------|------|
| `config.json` | 主配置（**勿提交 git**） |
| `.config.key` | Fernet 解密密钥（**勿提交 git**） |
| `config.json.example` | 无敏感信息的示例模板（可复制为 `config.json`） |

## 敏感字段加密

保存配置（设置页或 API）时，以下字段 **自动加密** 写入磁盘：

- `db_password`
- `magic_fox_password`
- `magic_fox_access_token`
- `api_token`

磁盘格式示例：

```json
"db_password": "enc:v1:gAAAAABl..."
```

- 首次加密保存时自动生成 `.config.key`（权限 600）
- 程序启动时自动解密，业务代码仍读明文
- 迁移服务器需 **同时拷贝** `config.json` 与 `.config.key`
- 可选环境变量 `DEFECTLOOP_CONFIG_KEY` 替代 `.config.key` 文件

未安装 `cryptography` 时会降级明文并打印警告：`pip install cryptography`。

## Magic-Fox 凭据

仅来自：

1. **config.json**（设置页保存，推荐）
2. **环境变量**：`MAGIC_FOX_TOKEN`、`MAGIC_FOX_ACCESS_TOKEN`、`MAGIC_FOX_USERNAME`、`MAGIC_FOX_PASSWORD`

不再读取 `~/.cursor/skills/` 下的 `.config` 或 `.token`。

## 主要配置项

### 数据库

| 字段 | 说明 |
|------|------|
| `db_host` / `db_user` / `db_database` | MySQL 连接 |
| `db_password` | 加密存储；设置页留空表示不修改 |

### 图片路径

| 字段 | 说明 |
|------|------|
| `img_path_mode` | `concat` 或 `full_path` |
| `img_base_path` | 拼接模式根目录 |
| `platform_root_drive` | 推断平台根目录盘符 |

### Magic-Fox

| 字段 | 说明 |
|------|------|
| `magic_fox_api_base` | API 根 URL |
| `magic_fox_auth_mode` | `password` 或 `token` |
| `magic_fox_username` / `magic_fox_password` | 账号密码（加密） |
| `magic_fox_access_token` | Token（加密） |
| `dataset_sync_root` | 本地同步目录，默认 `datasets` |

### DetUnify 预测

| 字段 | 说明 |
|------|------|
| `detunify_studio_root` | DetUnify-Studio 根目录 |
| `predict_python_executable` | 子进程 Python |
| `predict_script` | 可选，默认 `scripts/predict_job_worker.py` |

### 其他

| 字段 | 说明 |
|------|------|
| `forge_database` | 写库名，默认 `detforge` |
| `coco_visualizer_root` | COCOVisualizer 路径 |
| `api_token` | 非空启用 API 鉴权（加密） |
| `default_sql` | 自由查询默认 SQL |

筛选规则在 `strategies/*.json`，不在 `config.json`。

## 修改方式

1. **Web 设置页**（推荐）：`/config` → 保存配置  
2. **直接编辑** `config.json`：明文密码需下次保存才会加密；加密字段勿手改  

## 注意事项

1. JSON 须 UTF-8 合法  
2. 损坏时程序回退默认配置  
3. `.gitignore` 已包含 `config.json` 与 `.config.key`
