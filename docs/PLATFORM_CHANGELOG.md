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

（暂无）

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
