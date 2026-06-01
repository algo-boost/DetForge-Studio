# DefectLoop Studio 用户使用手册

**工业缺陷检测数据闭环系统**

DefectLoop Studio 面向产线缺陷数据运营：从平台库查询检测明细、规则/Python 筛选与采样、Magic-Fox 训练平台同步、DetUnify 在线/批量预测、人工质检归档，并导出 COCO / CSV。


---

## 目录

1. [快速开始](#1-快速开始)
2. [界面导航](#2-界面导航)
3. [首次配置](#3-首次配置)
4. [数据查询](#4-数据查询)
5. [样本图库与在线预测](#5-样本图库与在线预测)
6. [训练平台](#6-训练平台)
7. [模型管理](#7-模型管理)
8. [预测任务](#8-预测任务)
9. [人工质检](#9-人工质检)
10. [查询历史与策略](#10-查询历史与策略)
11. [导出与归档](#11-导出与归档)
12. [安全与运维](#12-安全与运维)
13. [常见问题](#13-常见问题)

---

## 1. 快速开始

### 启动服务

```bash
cd tools/DetForge-Studio
pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python app.py
```

浏览器打开：**http://localhost:5050**

### 开发模式（前端热更新）

```bash
# 终端 1
python app.py

# 终端 2
cd frontend && npm run dev
# 访问 http://localhost:5173（API 代理到 5050）
```

### 第一次使用建议顺序

1. **设置** → 数据库 / 图片路径 / Magic-Fox 认证  
2. **查询** → 选时段 → 预览筛选 → 执行查询  
3. **样本图库** → 浏览、筛选、改标注  
4. **训练平台** → 发现导入数据集 → 同步 COCO  
5. **预测任务** 或 **在线预测** → 跑模型  
6. **人工质检** → 客户图核对归档  

---

## 2. 界面导航

侧栏按 **场景** 分组；相关页面顶部有 **SceneHub** 标签可快速切换。

### 数据查询

| 菜单 | 路径 | 用途 |
|------|------|------|
| 查询 | `/` | SQL + 规则/Python 筛选；默认数据源为 **预测结果表**；结果可「归档此批」 |
| 查询历史 | `/history` | 执行记录，可恢复策略快照 |
| 人工质检 | `/manual-qc` | 客户图核对、SN 匹配、分类归档 |
| 筛选归档 | `/curation` | 批次出站/回传 COCO、训练 handoff、历史回跑 |

### 预测评估

| 菜单 | 路径 | 用途 |
|------|------|------|
| 在线预测 | `/online-predict` | **批量预测**（数据集 + 模型 → 后台作业）或 **临时上传对比**（DetUnify） |
| 预测任务 | `/jobs` | 批量预测/导出等后台作业进度与结果 |
| 模型 | `/models` | 本地注册表、训练平台模型、部署/训练权重 |

### 平台工具

| 菜单 | 路径 | 用途 |
|------|------|------|
| 训练平台 | `/training` | Magic-Fox 项目、数据集同步 |
| 样本图库 | `/viewer` | COCOVisualizer（筛选/EDA/改标注） |

### 设置

| 菜单 | 路径 | 用途 |
|------|------|------|
| 设置 | `/config` | 数据库、路径、Magic-Fox、预测环境、策略、手册 |

侧栏 **设置** 内分区：数据库、检测项目、类别映射、图片路径、样本图库、预测环境、Magic-Fox、安全、查询模板、系统状态、**查询策略**、**使用手册**。

首次配置：复制 `config.json.example` → `config.json`，或在设置页填写后保存。

---

## 3. 首次配置

进入 **设置**（`/config`）。

### 3.1 数据库

| 字段 | 说明 |
|------|------|
| 主机 / 用户 / 数据库 | 连接 `vision_backend` 平台库 |
| 密码 | 留空表示不修改已保存值；也可用环境变量 `DB_PASSWORD` |

点击 **测试连接** 确认可用。

### 3.2 图片路径

- **拼接模式**（默认）：`img_base_path` + SQL 结果中的 `origin_object_key`  
- **完整路径模式**：直接使用 `local_pic_url` 等字段  

若图片无法显示，点击 **从数据库同步路径**，或检查 `img_base_path` 目录是否存在。

### 3.3 检测项目（两套 Approach）

DetForge 同时使用 **两套互不相同的 Approach ID**，请勿混用：

| 配置位置 | 字段 | 用途 |
|----------|------|------|
| **设置 → 检测项目** | `defect_approach_id` | **本地总控**（vision_backend）：缺陷类别、查询筛选、**部署模型**（`modeldeploy`）、本地 `modeltrainconfig` |
| **训练平台 → 项目** | `sync_projects.approach_id` | **Magic-Fox 线上**：数据集同步、平台训练模型 API、labels |

示例：延锋门板 Magic-Fox 项目 `approach_id=598`，而本地已部署模型在 `modeldeploy.approach_id=18`。在线预测时：

- **部署模型 Tab** → 读取设置里的 `defect_approach_id`（如 18），可看到 125 个本地权重  
- **训练模型 Tab** → 需关联 Magic-Fox 项目（598），走线上验证 API  

- **defect_approach_id**：默认 18  
- **刷新类别** 从本地总控拉取最新标签  

### 3.4 Magic-Fox 训练平台

| 字段 | 说明 |
|------|------|
| magic_fox_api_base | 默认 `https://www.ai.magic-fox.com/api/v1` |
| 认证方式 | 账号密码 或 Access Token |
| dataset_sync_root | 本地数据集同步根目录（默认 `datasets/`） |

凭据**仅**保存在本机 `config.json`（加密）或环境变量 `MAGIC_FOX_*`，**不再**读取 Cursor Skills 目录。

点击 **测试认证** 成功后自动写入配置。

### 3.5 预测环境（DetUnify）

| 字段 | 说明 |
|------|------|
| detunify_studio_root | DetUnify-Studio 仓库根（默认同 monorepo sibling） |
| predict_python_executable | 含 torch 的 Python 解释器 |
| predict_script | 可选；默认 `scripts/predict_job_worker.py` |

- **在线预测**：内嵌 DetUnify Web UI，无需单独开 6006 端口  
- **预测任务**：通过上述子进程批量预测并写库  

### 3.6 配置加密

保存配置时，以下字段 **Fernet 加密** 写入 `config.json`：

- `db_password`
- `magic_fox_password` / `magic_fox_access_token`
- `api_token`

解密密钥在服务器本地 **`.config.key`**（首次保存时自动生成）。  
**两者均勿提交 git**；迁移机器需同时拷贝 `config.json` 与 `.config.key`。

可选：环境变量 `DEFECTLOOP_CONFIG_KEY` 指定密钥（部署场景）。

### 3.7 写库与安全（可选）

| 字段 | 说明 |
|------|------|
| forge_database | 写库名，默认 `detforge` |
| device_max_concurrency | 同 GPU 并发预测作业数，默认 1 |
| api_token | 非空时所有 `/api/*` 需鉴权 |

浏览器 Token：

```javascript
localStorage.setItem('pc_api_token', '你的令牌')
```

---

## 4. 数据查询

### 4.1 数据源

- **预测结果表**（默认）：`detforge.predict_result`，对已预测结果二次筛选  
  - 顶部 **预测批次** 下拉自动匹配最近完成的作业（`WHERE job_id = N`，**无需时段**）  
  - 从在线预测完成后跳转 `/?predict_job=N` 会自动载入该批次并提示  
- **检测明细表**：`product_detection_detail_result`，需选择时间范围  

### 4.2 基本流程

1. 选择 **数据源**（预测结果 / 检测明细）  
2. 预测结果表：选择 **预测批次**；检测明细：设置 **时间范围**  
3. 编辑 **SQL**（检测明细可用 `${START_TIME}` / `${END_TIME}`）  
4. **规则** / **代码** / **对照** 筛选  
5. **随机采样** 条数与种子  
6. **预览筛选** → **执行查询**（`Ctrl/Cmd + Enter`）  
7. **打开样本图库** 或导出  

### 4.3 筛选模式

| 模式 | 说明 |
|------|------|
| 规则 | 类别、置信度、剔除比例 → `apply_filter_rules` |
| 代码 | 手写 `process_data(df)` |
| 对照 | 规则表 + 代码并排 |

### 4.4 Pipeline 导入

从产线 Pipeline 导入最低阈值规则；面别写入 `positions` 字段。

---

## 5. 样本图库与在线预测

### 5.1 样本图库（COCOVisualizer）

- 侧栏 **样本图库** → `/viewer`，内嵌 `/viz`  
- 查询结果栏 **打开样本图库** → 加载 `exports/<task_id>/`  
- 预测任务结果：GT 为 `_annotations.coco.json`，预测为 `_annotations.<模型>.pred.coco.json`  
- 设置 → 样本图库：`coco_visualizer_root`、`viz_open_mode`（prompt / auto / off）  

### 5.2 在线预测（`/online-predict`）

两个 Tab：

| Tab | 说明 |
|-----|------|
| **批量预测** | 选数据集 + 模型（部署/训练 API/已注册），创建后台作业，结果写 `predict_result` |
| **临时上传对比** | 内嵌 DetUnify（`/unify`），上传模型与图片即时对比，**不落库** |

批量预测完成后会跳转 **查询页** 并自动匹配对应 `job_id`。  
与 **预测任务** 页配合查看进度、打开样本图库。

若「临时上传对比」不可用，检查设置页 `detunify_studio_root` 并 **重启 Flask**。

---

## 6. 训练平台

路径：**训练平台**（`/training`）

1. **设置** 中完成 Magic-Fox 认证  
2. **发现导入**：粘贴 Magic-Fox URL，批量添加底库/快照  
3. **数据集**：同步 COCO 到 `datasets/`，支持增量与溯源  
4. **模型预测**：勾选平台训练模型，走 Magic-Fox 线上 API  

平台模型列表通过 **从 Magic-Fox 同步** 抓取训练页（需 Playwright）。

---

## 7. 模型管理

路径：**模型**（`/models`）

### 本地注册表

登记权重路径、框架、阈值等；用于 **预测任务** 本地子进程预测。

### 训练平台模型

在 **训练平台** 页管理；走线上 API，**无需**导入权重到本地。

---

## 8. 预测任务

路径：**预测任务**（`/jobs`）

### 创建作业

1. 选择已注册模型  
2. 图片来源：查询 `task_id` / 目录 / 路径列表  
3. 创建 → worker 子进程 DetUnify 逐图预测写库  

### 作业状态

pending → running → done / failed / paused / canceled  

支持 **暂停 / 继续 / 取消 / 重试失败项**。

Worker 随 Flask 启动；独立运行：`python worker.py`。

---

## 9. 人工质检

路径：**人工质检**（`/manual-qc`）

1. 拖入客户图 → 输入 SN → 图廊选平台图  
2. 填缺陷类型、成像情况 → **归档**  
3. 按时段查询 → 导出目录或 ZIP  

详见原快捷键：`←/→` 切换候选、`N` 拍不到、`Ctrl+Enter` 归档。

---

## 10. 查询历史与策略

### 查询历史（`/history`）

查看过往执行、从 snapshot 恢复、存为策略。

### 查询策略（设置 → 查询策略）

- 策略 JSON 管理、块模板  
- 导出 / 导入  
- 内置策略如 `daily_trawl`、`fp_eval_set`  

---

## 11. 导出与归档

### 11.1 查询结果导出

| 格式 | 说明 |
|------|------|
| COCO ZIP | 标注 + 图片副本 |
| CSV | 表格字段 |
| 归档 | 复制到 `archive_base_path` |

预测结果二次利用：数据源选「预测结果表」→ 筛选 → 导出评测集。

### 11.2 筛选归档（`/curation`）

三条业务线共用 **筛选 → 外部 COCO 编辑 → 归档 → 训练交接** 闭环：

| 场景 | 入口 | intent |
|------|------|--------|
| 每日 NG 捞 | 查询结果 →「归档此批」 | `daily_ng` |
| 历史回跑 | 筛选归档页「开始回跑」或预测任务「回跑筛选批次」 | `replay_eval` |
| 人工质检 | 人工质检归档 → 筛选归档页「生成交接包」 | `customer_qc` |

**标准步骤（①②）**

1. **生成出站包**：`_annotations.coco.json` + `images/`
2. 外部工具（COCOVisualizer 等）编辑 COCO：删图/改框；在 `images[].extra` 写 `disposition`（如 `need_label`、`fp_model`、`fn_missed`）
3. **上传筛选后的 COCO**（不是改 manifest.csv）
4. **确认归档**
5. **生成交接包** → `datasets/training_inbox/<batch_code>/all_kept` 与 `to_label/`
6. 训练侧手动 ingest；Studio 标记「已交接」

**disposition 常用值**：`ng_confirmed`、`need_label`、`fp_model`、`fn_missed`、`tp_detected`

### 11.3 历史回跑向导（②）

路径：**筛选归档** → **开始回跑**，或 `/curation?replay=1&job_id=<预测作业ID>`

1. 选择已完成的 **predict** 作业  
2. 筛选模式：
   - **模型检出（有框）**：`box_count > 0`，误检 FP 复核  
   - **模型未检出（无框）**：漏检 FN 复核  
   - **全部预测结果**  
3. 可选最低 `max_score`、款型关键词 → 预览数量  
4. **创建筛选批次** → 自动 `replay_eval`，初始 disposition 已写入  
5. 后续同 11.2 出站/回传/交接流程  

**训练交接目录**（配置 `handoff_root`，默认 `datasets/training_inbox/`）：

```
training_inbox/
  cb_YYYYMMDD_.../all_kept/     # 全部保留样本
  cb_YYYYMMDD_.../to_label/     # need_platform_label 样本
  qc_YYYYMMDD_.../              # 人工质检 handoff
```

---

## 12. 安全与运维

### 12.1 环境变量

| 变量 | 说明 |
|------|------|
| `DB_*` | 数据库连接 |
| `MAGIC_FOX_TOKEN` / `MAGIC_FOX_ACCESS_TOKEN` | Magic-Fox Token |
| `MAGIC_FOX_USERNAME` / `MAGIC_FOX_PASSWORD` | Magic-Fox 账号（可选） |
| `DEFECTLOOP_CONFIG_KEY` | 配置加密密钥 |
| `PC_NO_WORKER=1` | 禁用内嵌 worker |
| `PC_WORKER_CONCURRENCY` | worker 并发 |
| `PC_MAX_CONTENT_MB` | 上传上限（默认 256MB） |

### 12.2 勿提交 git 的文件

| 路径 | 内容 |
|------|------|
| `config.json` | 本地配置（敏感字段已加密） |
| `.config.key` | 配置解密密钥 |
| `exports/` | 查询与导出 |
| `uploads/` | 人工质检客户图 |
| `datasets/` | Magic-Fox 同步数据集 |
| `.env` | 环境变量 |

### 12.3 初始化写库

首次使用预测/质检时，按提示 **初始化 detforge 库**，或 `POST /api/forge/schema/init`。

### 12.4 Worker 进程

批量预测、数据集同步、人工质检导出等 **后台作业** 由 `worker.py` 消费 `detforge.job` 表执行。

| 方式 | 说明 |
|------|------|
| 内嵌 worker | 默认 `python app.py` 会拉起 worker 子进程 |
| 独立 worker | 生产建议单独运行：`python worker.py` |
| 禁用内嵌 | 环境变量 `PC_NO_WORKER=1` |
| 并发 | `PC_WORKER_CONCURRENCY`（默认 1） |

日志：作业详情页 **运行日志** Tab；失败项见 **失败项** Tab。

一键开发：

```bash
chmod +x scripts/dev.sh
./scripts/dev.sh
```

Docker 仅 MySQL（应用仍本机运行）：

```bash
docker compose up -d mysql
```

---

## 13. 常见问题

### Magic-Fox Token 能同步但「发现数据集」报权限不足

部分 Access Token **仅有 `dataset_items/page` 读取权限**，无法调用 `datasets/page` 列表接口（approach 598 常见）。

DetForge 会自动降级：

1. 使用内置 catalog（如 `studio/sync/catalogs/approach_598.json`）中的数据集 ID  
2. 逐个调用 `dataset_items/page` 探测数量并展示  

若仍失败，可在 `config.json` 增加：

```json
"magic_fox_dataset_catalog": {
  "598": [
    {"id": 2845, "name": "延锋门板-缺陷集"},
    {"id": 3063, "name": "皮带线背景打标"}
  ]
}
```

训练快照列表（`generate_datasets/page`）可能仍无权限，发现时会跳过并提示，不影响底库数据集导入。

### 在线预测部署模型列表为空

1. 确认 **设置 → 检测项目 → defect_approach_id** 与 `vision_backend.modeldeploy.approach_id` 一致（常见为 18）  
2. 不要与 Magic-Fox 项目的 `approach_id`（如 598）混淆——后者只用于训练模型与数据集同步  
3. 检查数据库连接与 `platform_root` / 权重路径是否可解析  

### 在线预测显示查询页或空白

1. 硬刷新浏览器；确认 Flask 已重启（日志应有 `DetUnify 已挂载于 /unify`）  
2. 检查 `detunify_studio_root`  
3. 地址栏应为 `/online-predict`  

### Magic-Fox 凭据来源 skill_config

已废弃。请在 **设置 → Magic-Fox** 填写并保存；凭据来源应显示 `config`。

### 配置解密失败

`.config.key` 与 `config.json` 不匹配（换机器未拷贝密钥）。恢复备份或重新填写密码保存。

### 图片无法加载

检查 `img_base_path`、SQL 是否含 `origin_object_key` / `local_pic_url`。

### 构建后 503

`cd frontend && npm run build`。

---


*应用内 **设置 → 使用手册** 可阅读本文档。*
