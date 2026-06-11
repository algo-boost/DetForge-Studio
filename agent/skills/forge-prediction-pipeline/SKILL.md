---
name: forge-prediction-pipeline
description: DefectLoop Studio（DetForge-Studio 仓库）的模型预测升级方案与数据库设计（独立写库 detforge、后台作业框架、断点续跑、预测结果二次筛选、分层采样评测集、人工质检归档）。当在 tools/DetForge-Studio 中实现或讨论：模型预测任务、后台 worker、预测任务管理界面、导入模型列表、预测结果写库、SQL+Python 二次筛选、误检水平评测集（按款型分层采样）、人工质检图片查找归档，或涉及 detforge 库的 model_registry / job / job_item / predict_result / manual_qc 表时使用。
---

# DefectLoop Studio — 模型预测升级方案（已实现基线）

本 skill 是 **DefectLoop Studio**（仓库 `DetForge-Studio`）「模型预测」大升级的设计与落地基线。改动前先读它，按既定决策与表结构推进，避免重复讨论。**已落地**，下述模块均存在于仓库。

## 背景事实（影响实现）
- **DetUnify-Studio**（`tools/DetUnify-Studio/src/predict/`）：原 `predict.py` 用 subprocess 分发到 `predict_hq_det.py` / `predict_dino.py`，一次性写 COCO，不增量、不可续跑。已新增 `model_api.py` 暴露常驻模型 API（`detect_model_type` / `load_model` / `LoadedModel.predict_one`），保留原 CLI/Web 兼容。生产环境由 DefectLoop 配置 `predict_python_executable` 子进程调用 `scripts/predict_job_worker.py`。
- **DefectLoop Studio**（仓库 `DetForge-Studio`）：Flask + React SPA。`server/core.py:build_query_task` 把 SQL→Python 筛选→采样结果落到 `exports/<task_id>/`。`deployed_models.py` 能从库拼出权重绝对路径（`modeldeploy.object_key`）。DB 客户端为裸 pymysql，已加写库方法。
- **筛选管线复用关键**：`python_builtins.filter_df_by_ext` / `remove_empty_ext_rows` / `count_category_boxes` 与 `csv2coco` 都读 `ext` JSON 的 `original_predictions`，格式 `{name,confidence,type,points:[{x,y,w,h}]}`。**预测结果表 `ext` 同形**，零改动复用全部筛选/采样/导出逻辑。

## 已确认决策（不要再推翻，除非用户改口）
1. **DetUnify 整合**：`model_api.py` 暴露 `load_model` 一次 + `predict_one` 逐图；DetForge import 它，逐图写库可续跑。重型依赖（torch/cv2/ml_backend/hq_det）惰性导入，不影响 Flask 启动与单测。
2. **并发（默认均为 1 串行）**：任务级并发（worker 多 loop 线程，各任务独占一次模型加载）+ 任务内图片并发（`job.intra_concurrency`，共享一次模型加载）。
3. **Worker 启动**：Flask 启动自动拉起常驻 worker（`worker.maybe_start_in_process`，PID 文件防重复，`PC_NO_WORKER=1` 禁用）+ 命令行 `python worker.py [--concurrency N] [--once]`。
4. **二次筛选**：查询页加「数据源」下拉（检测明细表 / 预测结果表），预测结果表复用现有 SQL+Python 筛选。
5. **人工质检工作流**：客户图**拖拽上传导入**（存 `uploads/manual_qc/<日期>/`）→ 输入 SN 查该 SN 全部平台缺陷图（图廊）→ **人工点选**匹配图（或标记「拍不到」no_match）→ 标注**缺陷类型** `defect_type` + **成像情况** `qc_category`（可配置类别，默认 成像清晰/成像不清/拍不到）→ 归档。支持单条核对 + 批量（拖多图逐张填 SN/类别）。类别持久化在 `config.json`（`manual_qc_imaging_categories` / `manual_qc_defect_types`）。可按**时段 + 成像类别**查询并**导出图片到服务器目录**（`<目录>/<类别>/<SN>__<id>__platform|customer.<ext>` + `manifest.csv`，include=platform/customer/both）。
6. **库与前缀（本次变更）**：写库为**独立新库 `detforge`**（与平台库 `vision_backend` 同一 MySQL 实例），**表不加前缀**。配置项 `forge_database`（默认 `detforge`）。App 连接仍指向 `vision_backend`（只读 SQL 模板不变）；写库表用跨库限定名 `` `detforge`.`table` `` 访问，平台只读表（`product_detection_detail_result` / `modeldeploy` / `modeltrainconfig` / `approach`）用 `vision_backend.`。要求 DB 账号对 `detforge` 有读写权限。

## 架构
```
Flask (server/) ──enqueue──▶ detforge.job / job_item ◀──poll── worker.py (本进程线程/独立进程)
   │                              │                              │
   │ 查询页/任务管理 UI            │ 状态/进度/心跳                │ predict handler (forge_predict):
   │                              ▼                              │  model_api.load_model 一次
   └── 数据源=预测结果表 ──▶ detforge.predict_result(ext 同形) ◀─逐图写─│  predict_one → 写库 → 标记 done
                                  detforge.manual_qc ◀── manual_qc handler (forge_manual_qc, 按SN查 vision_backend)
```
- **作业框架**是底座：`job_type` ∈ `predict` / `manual_qc_archive` / `manual_qc_export`（预留 `sampling_export`）。
- **续跑**：worker 只取 `job_item.status in (pending,running)` 且 `next_retry_at` 已到期，重启自动跳过 `done`；按心跳超时回收僵死 running 作业为 pending。
- **进度**：`job.done/total` 实时更新，UI 轮询有活动作业时 3s、空闲退避到 12s。
- **设备调度**：`forge_predict` 按 `device` 维护信号量，`config.device_max_concurrency`（默认 1）限制同设备并发作业数，防 OOM。
- **失败退避**：`job_item` 失败回退 pending 并写 `next_retry_at = NOW()+attempts*30s`，避免坏图空转快速重试。

## 安全与运维（强化项）
- **路径白名单**（`forge_paths.py`）：`/api/image?path=` 只允许读 `img_base_path` / `uploads` / `exports`（及 `allowed_image_roots`）内文件，越权 403；导出 `out_dir` 必须落在 `exports/`（或 `manual_qc_export_roots`）内，否则 ValueError。
- **上传限制**：`MAX_CONTENT_LENGTH`（默认 256MB，`PC_MAX_CONTENT_MB` 可调）+ 单次 ≤500 张。
- **口令**：`DB_PASSWORD` 等环境变量优先于 `config.json`；`config.json` 与 `uploads/` 已进 `.gitignore`。
- **可选鉴权**：`config.api_token` 非空时，所有 `/api/*` 需 `X-API-Token` 头或 `?token=`；前端从 `localStorage.pc_api_token` 注入（`getApiToken`/`setApiToken`）。默认关闭。
- **DB 线程安全**：`MySQLClient` 用 `RLock` 串行化所有读写，修复 worker 多线程共享单连接的竞态；`ping(reconnect=False)` 去除弃用告警。
- **Worker 可观测**：`logging`（`detforge.worker`，`PC_WORKER_LOGLEVEL`）记录作业开始/耗时/异常。

## 数据库设计（DDL 见 [schema.sql](schema.sql)）
独立库 `detforge`，5 张表，**无前缀**：
- `model_registry`：导入/登记的模型（框架/子类型/权重路径/labels/来源/默认参数）。
- `job`：通用作业（params JSON、status 状态机、priority、intra_concurrency、total/done/failed、worker_id、heartbeat）。
- `job_item`：作业项（断点续跑粒度；`uk_job_ref` 去重）。
- `predict_result`：**一图一行**，`ext` JSON 与平台同形；带 SN/product_type/product_id/position/img_path。
- `manual_qc`：人工质检归档（客户图 + SN → 匹配到的平台缺陷图 + 缺陷信息 + 状态）。

状态机：
- `job.status`: pending → running →(paused) → done | failed | canceled
- `job_item.status`: pending → running → done | failed | skipped

## 代码落点（已实现）
- 写库数据层：[studio/forge/forge_db.py](../../../studio/forge/forge_db.py)（`ensure_schema`/`schema_ready`、模型/作业/作业项/预测结果/质检 CRUD、`claim_next_job`/心跳/续跑、跨库限定名 `_t`）。
- DB 写方法：`server/core.py:MySQLClient`（`execute`/`execute_returning_id`/`executemany`/`fetchall`/`fetchone`/`execute_script`）+ 配置 `forge_database`。
- 模型 API：`tools/DetUnify-Studio/src/predict/model_api.py`（`load_model`/`LoadedModel.predict_one`，输出 ext 同形）。
- 预测处理器：[forge_predict.py](../../../forge_predict.py)（`run_predict_job`→`_run_with_loaded`，逐图写 `predict_result`、失败按 `attempts` 重试、`intra_concurrency` 线程池、`_device_sem` 设备信号量、`health_check_model` 健康检查、支持 `model_loader` 注入测试）。
- 作业编排/模型导入：[forge_service.py](../../../forge_service.py)（`enqueue_predict_job`、`enqueue_export_job`、`import_model`、`infer_framework`、从 task_id/dir/paths 构建 items + items_meta）。
- 人工质检：[forge_manual_qc.py](../../../forge_manual_qc.py)（`find_platform_records_by_sn`(limit 分页) 查 `vision_backend`、`_fetch_detail_record`、`archive_one`(`matched_detail_id`/`no_match`/`defect_type`/`qc_category`，返回 `duplicate_of` 去重提示)/`archive_batch`、`get_categories`/`save_categories`(含 `defect_strict`)、`export_records`(时段+类别+缺陷类型拷图，`as_zip` 打包)、`cleanup_orphan_uploads`(清理未引用客户图)）。客户图上传走 `POST /api/forge/manual-qc/upload`（存 `uploads/manual_qc/<日期>/`），预览复用 `/api/image?path=`。
- 路径安全：[forge_paths.py](../../../forge_paths.py)（`safe_read_path`/`safe_export_dir`/`is_within`）。
- Worker：[worker.py](../../../worker.py)（`WorkerManager` 多 loop 线程、`_dispatch` 心跳+stop_check+日志、`_run_manual_qc_export_job` 异步导出、`maybe_start_in_process`、CLI）。
- 路由：`server/routes/forge.py`（`/models*`+`/models/<id>/health`、`/jobs*`+`/jobs/<id>/items`+`/jobs/<id>/results`、`/predict-result/<id>/preview`(带框 PNG)、`/predict-result/source`、`/manual-qc`(GET 过滤+分页 offset/total；POST 归档)、`/manual-qc/<id>`(PATCH/DELETE)、`/manual-qc/lookup`、`/manual-qc/upload`、`/manual-qc/categories`、`/manual-qc/export`(async/as_zip)、`/manual-qc/cleanup-uploads`）。鉴权在 `server/factory.py:_install_optional_auth`。
- 采样：`python_builtins.stratified_sample_by_type(df,n,type_col,seed)`，已注入命名空间；内置策略 `strategies/_builtin/fp_eval_set.json`「误检水平评测集」。
- 前端：`frontend/src/pages/JobsPage.jsx`（任务管理+建预测作业+`JobDetail` 失败项/带框结果预览+`manual_qc_export` 导出下载+作业分页+轮询退避）、`ManualQcPage.jsx`（核对/批量/查询导出/类别配置/编辑删除/对比 lightbox/强制归档/图廊快捷键）、`ModelsPage.jsx`（注册表/导入/健康检查）、`QueryPage.jsx`（数据源=预测结果表时带框预览，`predict_result_id`）；路由 `App.jsx`（全部页面 `React.lazy`，主包 ~240KB + `ErrorBoundary`）；`frontend/src/lib/resultImage.js`；API 客户端含 `forgeExportDownloadUrl`。
- 测试：`test_forge.py`（分层采样/schema(含新列)/framework/ext 形状/`forge_paths`/人工质检 archive(no_match/去重)/export/cleanup 纯逻辑 + 需 MySQL 的作业/续跑/归档集成，库 `detforge_test`）；前端 `frontend/src/utils/format.test.js`（`npm test` / `vitest run`）。

## 实现约定
- 新后端模块放 `tools/DetForge-Studio/studio/` 对应子包，路由进 `server/routes/forge.py`。
- 前端新页面进 `frontend/src/pages/`，注册到 `App.jsx` 路由与 `Layout` 导航；API 进 `frontend/src/api/client.js`。
- 改完跑 `python3 -m pytest -q` 与 `cd frontend && npm run build`。
- 预测结果表 `ext` 必须与平台同形，否则筛选管线复用失效。
- 写库表 SQL 一律走 `forge_db._t(table)` 生成的限定名，不要硬编码库名。
