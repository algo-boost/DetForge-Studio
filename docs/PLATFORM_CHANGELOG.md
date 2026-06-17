# IISP 平台功能变更记录

**版本**：v1.0  
**维护**：**任何平台功能变更必须与代码同一 PR 更新本文 `[Unreleased]`**  
**约束 Skill**： [`.cursor/skills/iisp-record-platform-change/SKILL.md`](../.cursor/skills/iisp-record-platform-change/SKILL.md)

> 本文记录 **对用户、L1/L2 角色、API、Tool、Flow、部署可见** 的变更。  
> 纯内部重构且行为不变 → 可不记，但须在 PR 说明「无用户可见变更」。  
> 架构定稿变更另记 `IISP_DESIGN_FINAL.md` 修订记录；Catalog 专项可记 `iisp-catalog/CHANGELOG.md`。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

### Changed

- **流水线 · 整体布局（L2）**：侧栏与页内 Hub 统一为「组合编排 / 流水线目录 / 编排助手 / 执行历史」四项；新增 `FlowsSceneShell` 统一流水线场景页壳；组合编排页改为三栏布局（左模块库、中步骤链、右运行设定与定时）；流水线目录标题与 Tab 文案收敛；执行历史链接 `flow_*` 直达组合编排并带 `?flow=` 参数。
- **组合编排 · 交互优化（L2）**：步骤链支持手风琴/全部展开/全部收起；右栏「运行设定」可隐藏以扩大编辑区；运行参数与定时文案简化，脚本与预览收入「高级选项」。
- **流水线目录 · 我的流水线（L2）**：目录页「流水线」Tab 合并展示「我的流水线」与「Catalog 模板」；支持从目录打开已保存 `flow_*`；页头新增「新建流水线」入口；组合编排工具栏增加「目录」快捷链接。
- **执行历史 · 统一入口（L2）**：新增 `FlowRunsHistoryPanel` 聚合待人工卡点、状态筛选与运行列表；`/flows?tab=history` 为唯一主入口（`/flows/runs` 保留重定向并传递查询参数）；工作台「Flow 卡点」改为「流水线运行」快照并链至执行历史；待办列表不再重复展示流水线人工卡点；摘要卡片「待人工 / 运行中」可点击跳转。

### Removed

- **Kestra 编排全移除**：删除 Kestra JVM 服务、Hub 客户端、`/flows/kestra` Studio、`/api/flows/kestra/*`、`/kestra-embed` 代理及 `iisp-catalog/pipelines/kestra/`；`deploy start` 仅启动 IISP；主编排路径为 **组合编排 + workflow_engine**；Legacy Catalog Pipeline 与 demo Flow 保留；编排助手改为产出 legacy nodes YAML。

### Added

- **流水线 · 组合编排 MVP**：新增 `/flows/compose` 主入口，固定「查询 → 预测」两步；每步复用与查询页/预测页相同的策略、时间窗、模型等表单控件；`task_id` 由引擎从上一步自动注入。运行走现有 `POST /api/forge/workflows/runs` + `workflow_engine`。
- **流水线导航**：侧栏「组合编排」为流水线默认项；原 Kestra Flow 目录收为「高级编排（Kestra）」，Kestra Studio / 编排助手 / 执行历史保留。

### Fixed

- **组合编排 · 执行详情**：修复 forge 自研 workflow（`custom_*` 模板）在 `/flows/runs/workflow:*` 详情页报「Flow 未找到」、流程图无法展示的问题（`get_flow_graph` / `get_flow_run` 回退读取 `workflow_template` 表并合并步骤状态）；pending 实例打开详情时自动尝试继续推进。
- **组合编排 · 运行卡住 pending**：修复 `create_workflow_run` 误调不存在的 `MySQLClient.last_insert_id()` 导致 INSERT 后抛 500、step_run 未创建、引擎线程未启动的问题（改用 `execute_returning_id`）；打开详情时自动补建缺失 step 并继续推进。
- **组合编排 · 任务详情**：修复 `/flows/tasks/custom_*` 因不在 Kestra Catalog 而永久「加载中」；`custom_*` 模板纳入 Flow 列表只读展示，并引导至组合编排页。
- **组合编排 · 模块组件化**：查询/预测/预测结果查询/筛选创建·导出·导入·归档/人工卡点/通知等步骤统一注册为可组合模块；组合编排页支持从模块库添加、排序、移除，自动绑定上游 task_id / job_id / batch_id；创建 run 后自动 repair 并推进，修复长期「排队」。
- **组合编排 · 完整业务 UI**：每步嵌入与业务页相同的配置界面——查询步为完整 QueryPage（策略/SQL/规则/Python/环境参数/预览）；预测步为 PlatformPredictPanel（项目/模型/阈值/设备）；筛选创建等为与筛选页一致的多段配置卡片；配置序列化为 workflow params（含 `strategy_snapshot`），不再使用简化 schema 表单。
- **组合编排 · 滚动与上游接入**：修复组合编排页无法向下滚动的问题；每步顶部展示「自动接入上游」条（task_id / job_id / batch_id）；预测步与预测结果查询步在存在上游时隐藏手动填写入口，运行时由引擎注入。
- **组合编排 · 流水线持久化**：保存可复用 `flow_id`（如 `flow_daily_fp`）；步骤 ID 统一为 `{flow_id}.s01` 格式；支持加载已保存流水线；`query → predict → query_predict → …` 链路上游自动绑定；修复 `{{params.time_window}}` 对象模板解析。
- **组合编排 · 定时调度**：组合编排页内可直接配置 cron 定时（preset + 自定义）；保存调度时同步流水线定义与运行级 env 设定；支持启用/停用、查看下次运行时间、立即触发；API：`GET/PUT /api/forge/workflows/compose-flows/{flow_id}/schedule`。
- **组合编排 · 运行级 env 模板推导**：页头「运行级设定」改为选择推导模板（快捷时段 / 相对偏移 / 固定绝对时段）并填写入参；每次运行 / 定时触发时执行内置脚本生成全局 env（含 START_TIME、END_TIME），注入全部查询步（**最高优先级**）；支持额外静态 env 覆盖同名键；旧 `time_window` 配置自动迁移为 `env_spec`；定时仅更新 cron 时保留已有 run params；API：`GET /api/forge/workflows/run-env-templates`、`POST /api/forge/workflows/run-env/preview`；与流水线一并保存为 `run_params_defaults.env_spec` + `env`。

- **数据查询 · 预测结果**：修复预测作业列表 API（`GET /api/forge/jobs?job_type=predict&status=done`）在 `job.params` 含大量 `items_meta` 时 MySQL sort buffer 溢出导致 500，进而无法加载预测批次与结果表的问题（`forge_db.list_jobs` 改为先按 id 分页再取精简字段）。
- **数据查询 · 执行失败**：默认 Python 不再强制调用 `apply_filter_rules`；规则模式未配置规则时允许仅执行 SQL；策略 `filter_rules_code` 在规则 UI 未加载时仍可回退使用。
- **样本图库**：补齐 `flask-cors` 依赖（COCOVisualizer 挂载所需），修复 `/viz` 未挂载导致无法打开样本图库的问题。
- **样本图库 · 黑屏**：构建 `packages/coco-visualizer/frontend` Vite 产物；修复兜底模板中 React vendor 脚本未带 `/viz` 前缀及 API 路径未加挂载前缀的问题。
- **数据查询 · 提交提示**：修复提交查询后「提示」弹窗正文为空（`showInfoModal` 等误用字符串参数）。
- **数据查询 · 误报中断**：修复每次轮询/提交触发 `create_app()` 重复执行 `init_query_jobs`，将进行中的查询误标为「服务已重启，任务已中断」的问题。
- **样本图库 · 打开慢 / 黑屏**：查询结果页点击「打开样本图库」先跳转 `/viewer` 再在页内异步准备（不再长时间阻塞在查询页）；iframe 等待 React 挂载后再隐藏加载层；复用同任务 viz session 与 `.coco` 缓存跳过重建；COCO 已有宽高时跳过 Pillow 逐张探测。
- **中断作业弹窗**：修复 `GET /api/lifecycle/interrupted-jobs` 在 job.params 过大时 MySQL sort buffer 溢出导致 500（`list_interrupted_jobs` 改为先查 id 再取字段）。
- **控制台 404**：Layout 预热仅在 DetUnify 已挂载时请求 `/unify/`，未配置时不再误报 404。
- **在线预测**：补齐 `requests` 依赖；Magic-Fox 部署编码 `DET0307` 等可正确识别为 `hq_det`；训练模型列表在平台同步失败时回退本地 `modeltrainconfig`。
- **流水线 / 编排助手**：补齐 `PyYAML` 依赖，修复 Flow 图与编排助手 API 因缺少 yaml 模块返回 500。
- **Kestra 嵌入**：IISP 启动时注入 `KESTRA_URL`（与 `deploy/native/env.defaults` 端口一致）；未设环境变量时 `kestra_client` 回退读取默认 8090，修复 embed 代理连错 8080 导致「Kestra 不可达」。
- **Kestra Flow 404**：`deploy start` 与执行前自动将 `iisp-catalog/pipelines/kestra/*.yaml` 导入 Hub（MySQL repository 下目录 watch 不可靠）；修复 `closed_loop_demo_smoke` 等 Flow「Requested Flow is not found」。

## [1.3.0] — 2026-06-11

### Added

- **M1 Gateway**：`GET /v1/tools`、`POST /v1/tools/{id}/invoke`（Contract v1，供 Kestra 调用）
- **L1 工作台**：`GET /api/workbench/todos`、`/summary`；默认首页 `HomePage`
- **Kestra 本地部署**：`deploy/docker-compose.kestra.yml` + [`deploy/README.md`](../deploy/README.md)
- **CLI**：`iisp skill validate|pack`、`iisp flow list-kestra`
- **流水线页**：`/flows`（Catalog Kestra Flow 只读）
- **实施路线图**：[`docs/IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md)
- **数据查询 Tool（query）** — L1/L2 查询、策略、历史统一为单工具 `query`（`action` 路由）
  - 技术：`tools/query/`（capability、REST 薄代理、`/v1/tools/query/invoke`）；`POST /api/query-tool/invoke` 兼容包装
  - 独立部署：`bash scripts/query-standalone.sh` → `:6021`（UI + REST + invoke）
  - 文档：[`tools/query/ui/README.md`](../tools/query/ui/README.md)
- **工具 UI 集成三态** — Shell 可按配置切换 embedded / remote / standalone（L2 运维可配 `config.json`）
  - 技术：`server/tool_integration.py`；`GET /api/tools/<tool_id>/integration`；legacy：`/api/query-tool/status`、`/api/viz/status`、`/api/unify/status`
  - config 键：`query_tool`、`viz_tool`、`unify_tool`（字段：`integration`、`remote_url`、`standalone_url`）
- **ToolHost 前端框架** — 统一 embedded 直渲染 / 本地挂载 iframe / remote iframe
  - 技术：`ToolHost`、`ToolEmbed`、`useToolIntegration`；注册表 `frontend/src/config/toolIntegration.js`
  - Query：`QueryToolHost`（embedded 默认无 iframe，lazy 加载 Query 页面）
  - 样本图库：`VizToolHost`（`/viewer`；session/src/preparing 参数行为不变）
  - 临时上传对比：`UnifyToolHost`（`/online-predict?tab=quick`）
- **Flow 目录触发 Kestra（F1）** — L2 在 `/flows` 填 Flow inputs 并运行，跳转 Kestra 执行详情
  - 技术：`POST /api/flows/kestra/execute`；`orchestration/kestra_inputs.py` 解析 YAML inputs
  - 文档：[`FLOW_UI_CONFIG_ROADMAP.md`](./FLOW_UI_CONFIG_ROADMAP.md) F1 ✅

### Changed

- **数据查询页** — 默认 embedded 集成，Shell 内直接加载 React 页面，加载更快（L1/L2）
  - 原 iframe 预检逻辑移除；remote 模式仍可通过 `query_tool.integration: remote` 启用
- **样本图库 / DetUnify 嵌入** — `/viewer`、`在线预测 → 临时上传对比` 改走 ToolHost，不再页面内硬编码 iframe 与手写 status 请求
  - L1 行为不变；L2 可配置 viz/unify 独立部署地址
- **Query REST** — `/api/query*`、`/api/strategies*` 转发至 `tools/query/rest.py` 统一 dispatch
- **前端体验整改批次（2026-06-11，多为内部重构，用户可见点见 Fixed）**
  - 样式架构按域拆分：`styles/app.css`（7264 行）拆为 `styles/domains/*.css` 12 个文件（base/layout/home/flows/query-panels|editor|results/admin/forge-predict|review|history/workflow），入口仅做有序 `@import`；产物 CSS 与拆分前字节级一致（哈希不变），无视觉变更
  - 状态文案统一：流程图节点/节点详情统一走 `components/ui/statusMap`，消除 3 处硬编码与文案不一致；时长/时间格式化抽到 `lib/time`（`formatDuration`/`formatDateTime`）复用
  - 轮询统一：新增 `hooks/usePolling`，收敛 6 处 `setInterval`（FlowRunDetail/Workflows/FlowRuns/FlowsCatalog/AppTopNav/JobWidgets）+ 重构 `useHumanGates`；标签页隐藏暂停、可见恢复、卸载清理、callback ref 化避免定时器抖动
  - SPA 内跳转：`/flows` 运行/详情跳转由 `window.location.href` 改 `useNavigate`，不再白屏重载（L1/L2）
  - 流式请求封装：新增 `api.streamRequest`/`api.flowAgentComposeStream`，编排助手 SSE 不再裸 `fetch`，统一 `X-API-Token`/`VITE_API_BASE`/错误提示
  - 构建分包：Vite `manualChunks` 拆出 `vendor-codemirror`/`vendor-react`/`vendor-router`/`vendor-marked`；首屏入口约 293KB→62KB，非编辑器页不再下载 480KB CodeMirror

### Deprecated

- **`query-strategy` 工具 id** — 合并入 `query`；旧 invoke 路径仍可用，新开发请只用 `query`
- **`useQueryIntegration`** — 改用 `useToolIntegration('query')`
- **`QueryToolEmbed` 页面** — re-export `ToolEmbed`；新路由请用 `QueryToolHost` / `ToolHost`

### Removed

- **重复/死代码 StatusPill** — 删除转发壳 `components/forge/jobs/StatusPill.jsx` 与失效的 `components/forge/jobs/jobUtils.js`；`JobWidgets`/`JobsList` 直接用统一 `components/ui/StatusPill`，`STATUS_LABEL` 改为就地派生自 `STATUS_MAP`

### Fixed

- **Query 工具 UI「未就绪」** — Vite 代理补 `/tools/query`；SPA 路由排除挂载路径；embedded 默认路径不再依赖 iframe 预检（L1/L2）
- **离线/无网环境可用（字体）** — 移除 `styles/app.css` 的远程 Google Fonts `@import`，改用本地 `@fontsource/dm-sans` + `@fontsource/jetbrains-mono`（`src/main.jsx` 引入，font-family 与 `tokens.css` 一致）
  - 技术：构建产物不再含 `fonts.googleapis.com`，18 个 woff2 本地打包；无公网时仍保留品牌字体（L1/L2）；新增依赖 `@fontsource/dm-sans`、`@fontsource/jetbrains-mono`

### Security

- （暂无）

### Docs

- 建立 `PLATFORM_CHANGELOG.md` 与 **iisp-record-platform-change** Skill
- 安装 [Karpathy guidelines](https://github.com/forrestchang/andrej-karpathy-skills)：`karpathy-guidelines.mdc` + Skill（通用编码约束）
- 新增 **iisp-unit-tests** Skill：功能实现必须与单元测试同 PR 交付
- **工具集成变更摘要**：本节 Added/Changed（query 单工具 + ToolHost + integration API）；路线图 M3-toolhost 见 [`IMPLEMENTATION_ROADMAP.md`](./IMPLEMENTATION_ROADMAP.md)
- **前端体验整改批次（2026-06-11）**：围绕「流畅/稳定/低耦合/风格统一/离线可用」，详见本节 Changed/Removed/Fixed；全程构建通过、`vitest` 83/83、无 lint

---

## [2026-06-09] — 文档与标准 v2.2

### Docs

- **架构定稿 v2.2**：编排统一 **Kestra**（Edge + Hub）；废弃 Windmill、cron 生产路径
- **用户分层**：L1（交付/客户质检，只用）/ L2（SA/算法/光学，配置）
- **Skill-first**：L2 通过 Platform Skill 扩展 Tool（`SKILL_PLATFORM.md`）
- 新增 [`DOCS_INDEX.md`](./DOCS_INDEX.md) 作为文档入口
- 产品能力地图对齐飞书《数据闭环建设方案评审》子模块 + 组合模块

---

## 条目写法（复制模板）

```markdown
### Added | Changed | …
- **[模块/Tool/页面]** 一句话用户可感知说明（L1/L2 谁受影响）
  - 技术：`tool_id` / API 路径 / Flow id（可选）
  - 文档：已同步 `PRODUCT_DESIGN` §x / `USER_GUIDE`（如适用）
```

---

## 变更类型 → 必同步文档

| 变更类型 | 必更新 | 建议更新 |
|----------|--------|----------|
| 新 Tool | 本文 + `releases.yaml`（若上线） | `PRODUCT_DESIGN` §6、`skills-index.yaml` |
| 新 Kestra Flow | 本文 + `releases.yaml` | `PRODUCT_DESIGN` §3.3 |
| API `/v1` 变更 | 本文 + OpenAPI | `IISP_PLATFORM.md` |
| L1/L2 导航/权限 | 本文 | `PRODUCT_DESIGN` §4、`UI_REDESIGN_CHECKLIST` |
| 架构决策 | 本文（摘要） | `IISP_DESIGN_FINAL` 修订记录 |
| 安全/Token | 本文 `Security` | `SECURITY.md` |
| 仅文档 | 本文 `Docs` | `DOCS_INDEX`（若增删文档） |

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 首版；与 iisp-record-platform-change Skill 配套 |
| v1.3.0 | 2026-06-11 | 定版：前端体验整改（流畅/稳定/低耦合/风格统一/离线可用）+ 平台变更快照 |
