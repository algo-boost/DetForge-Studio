# DetForge Studio 测试矩阵

本文档映射产品功能点 ↔ 自动化测试 ↔ 建议的手动验证步骤。

## 运行方式

```bash
# Python（项目根）
PC_NO_WORKER=1 pytest tests/ -q

# 前端
cd frontend && npm test && npm run build

# 浏览器 E2E（5051 端口，API mock，无需 MySQL）
cd e2e && npm ci && npx playwright install chromium && npm test
```

## 功能覆盖一览

| 功能域 | 用户可见能力 | 自动化测试 | 手动验证要点 |
|--------|-------------|-----------|-------------|
| **配置** | 数据库/Magic-Fox/路径/Token | `test_api_feature_matrix.py::TestConfigAndDocs` · `test_config_crypto.py` | 保存配置、测试连接、敏感字段不回显 |
| **使用手册** | 设置页内嵌文档 | `test_api_feature_matrix` user-guide | `/config?section=docs` 渲染 Markdown |
| **数据查询** | SQL、时间变量、Python/Flow 筛选、采样 | `test_api_feature_matrix::TestQueryApi` · `test_flow_compiler.py` · `test_pipeline_rules.py` | 执行查询、规则筛选、随机采样、历史恢复 |
| **查询结果** | 表格筛选、大图库、导出 | `resultFilters.test.js` · `constants.test.js` | ≥500 条提示、筛选器、打开样本图库 |
| **策略** | 保存/加载/执行策略 | `test_api_feature_matrix::TestStrategiesAndFlow` | 策略页 CRUD、一键执行 |
| **Flow 编排** | 节点编译、采样函数 | `test_flow_compiler.py` · feature matrix flow tests | Flow 编辑器编译、预览 Python |
| **导出/归档** | COCO ZIP、CSV、平台归档 | `test_csv2coco.py` · `test_pred_coco_export.py` · export 404 tests | 选中导出、pred/GT 侧车 |
| **图片 API** | 白名单路径、占位图 | `TestImageSecurity` | 非法路径 403、缺失文件占位 PNG |
| **预测批次** | job_id SQL、批次标签 | `predictJob.test.js` · `test_predict_batch.py` | `/?predict_job=N` 自动查询、批次下拉模型名 |
| **在线预测** | 批量/DetUnify | `test_predict_runtime.py` · forge predict POST tests | 上传图片、提交作业、查看进度 |
| **预测结果** | pred/GT 看图 | `test_pred_coco_export.py` · `test_viz_bridge.py` | 结果页打开 viz、侧车 JSON |
| **模型管理** | 注册/启停/健康检查 | forge models GET/POST tests | 模型列表、导入平台模型 |
| **预测任务** | 作业列表/日志/控制 | forge jobs tests | `/jobs` 列表、取消/重试 |
| **人工质检** | 上传/SN 匹配/分类/导出 | forge manual-qc tests · `format.test.js` | 上传、lookup、导出 CSV |
| **训练平台** | 项目/数据集/同步 | `test_sync.py` · `test_dataset_provenance.py` | `/training` 同步、数据集 viz |
| **样本图库** | viz 挂载、session | `test_viz_bridge.py` · `sampleGallery.test.js` | viz 未挂载时的错误提示 |
| **DetUnify** | 在线推理桥接 | unify status test | `/online-predict` DetUnify 模式 |
| **SPA 路由** | 各页面 History fallback | `test_api_feature_matrix` SPA tests | 刷新 `/models`、`/training` 不 404 |
| **浏览器 E2E** | 查询→导出→预测→质检全链路 | `e2e/tests/full-chain.spec.js` · `e2e/tests/navigation.spec.js` | `cd e2e && npm test` |
| **筛选归档** | 捞图批次、COCO 回传、训练交接 | `tests/test_curation.py` · `tests/test_dispositions_handoff.py` · `/curation` | 改 COCO → 上传 → 归档/交接 |
| **历史回跑向导** | predict job → replay_eval 批次 | `tests/test_replay_eval.py` · `e2e/tests/curation-replay.spec.js` | 向导预览/创建、任务页入口 |
| **历史记录** | 筛选/分组/恢复 | `historyUtils.test.js` | `/history` 时段筛选、按策略分组 |
| **时间预设** | 今天/昨天/7天/30天 | `time.test.js` · `historyUtils` | 查询页时间快捷按钮 |

## 测试文件索引

### Python (`tests/`)

| 文件 | 侧重 |
|------|------|
| `test_api_feature_matrix.py` | **全路由 smoke + 校验**（新增，约 60+ 用例） |
| `test_pred_coco_export.py` | pred/GT 分层 COCO 导出 |
| `test_e2e_api.py` | 需 live server 5050 的 E2E（可选） |
| `test_forge.py` | detforge 库集成（需 MySQL） |
| `test_flow_compiler.py` | Flow IR → Python |
| `test_predict_batch.py` | 批次 SQL / slug |
| 其余 | 注解解析、同步、配置加密等单元测试 |

### 前端 (`frontend/src/**/*.test.js`)

| 文件 | 侧重 |
|------|------|
| `lib/constants.test.js` | SQL 构建、采样函数、阈值 |
| `lib/resultFilters.test.js` | 结果表筛选逻辑 |
| `lib/predictJob.test.js` | 批次解析与标签 |
| `lib/sampleGallery.test.js` | 图库错误文案 |
| `lib/historyUtils.test.js` | 历史筛选/分组 |
| `lib/consoleOutput.test.js` | Python 控制台解析 |
| `lib/time.test.js` | 时间预设 |
| `utils/format.test.js` | 归档条目、SQL 时间 |

### 浏览器 E2E (`e2e/`)

| 文件 | 侧重 |
|------|------|
| `tests/full-chain.spec.js` | 查询 → 导出 COCO → 在线预测 → 任务列表 → 人工质检 |
| `tests/navigation.spec.js` | 侧栏路由、Hub Tab 切换 |
| `fixtures/mock-api.js` | Playwright 路由 mock（无 MySQL） |

```bash
cd e2e && npm install && npx playwright install chromium && npm test
```

E2E 服务默认端口 **5051**（`scripts/e2e-server.sh`），与开发 5050 隔离。

## 需 MySQL / 外部服务的用例

以下用例在 CI 无 DB 时可能跳过或仅测 JSON 错误形态：

- `test_forge.py` — 需 `detforge_test` 库
- `test_sync.py` — Magic-Fox 凭据
- `test_e2e_api.py` — 5050 端口 live server

本地完整验证建议：`docker-compose up -d` 启动 MySQL 后跑 `pytest tests/test_forge.py`。
