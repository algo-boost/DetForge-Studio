# IISP UI 改造实施清单

**版本**：v1.6  
**标准**：[`DOCS_INDEX.md`](./DOCS_INDEX.md) · v2.2（Kestra · L1/L2）

本文是**可执行 checklist**：按阶段 U1→U5 排列，含路由、组件、API、验收标准。  
**技术约束不变**：React 19 + Vite 6 + 现有 CSS token；不迁 umi；不做 Electron。

---

## 总览

| 阶段 | 主题 | 预估 | 依赖 |
|------|------|------|------|
| **U1** | 工作台 + 待办聚合 | 3–5 天 | 少量新 API |
| **U2** | L1/L2 分层导航 + 场景 Hub | 2–4 天 | U1 可选并行 |
| **U3** | 流水线页（Catalog 只读） | 4–6 天 | Catalog sync 已有 |
| **U4** | 工具箱分层 + 统一状态组件 | 2–3 天 | — |
| **U5** | 设计系统 + Command Palette + 角色视图 | 3–5 天 | U2 |

---

## U1 — 工作台（Home）+ 待办

### 1.1 目标

用户打开系统第一眼看到：**待办、进行中 Flow、最近查询**；人工卡点可一键跳转业务页。

### 1.2 路由

| 项 | 现状 | 目标 |
|----|------|------|
| `/` | `QueryPage` | **`HomePage`**（新） |
| `/query` | 无 | 原查询页迁至此 |
| 兼容 | — | `/` 旧书签可保留 301 或设置「默认首页」配置 |

**`App.jsx` 改动要点**

```text
+ import HomePage from './pages/HomePage'
+ import QueryPage（路径改为 /query）
  <Route index element={<HomePage />} />
  <Route path="query" element={<QueryPage />} />
```

### 1.3 新建文件

| 文件 | 职责 | 状态 |
|------|------|------|
| `frontend/src/pages/HomePage.jsx` | 工作台三栏布局 | ✅ |
| `frontend/src/components/home/TodoList.jsx` | 待办列表 | ✅ |
| `frontend/src/components/home/ActiveFlowsPanel.jsx` | 进行中 / waiting_human Flow | ✅ |
| `frontend/src/components/home/RecentQueriesPanel.jsx` | 最近查询（复用 QueryJobsContext） | ✅ |
| `frontend/src/components/home/QuickActions.jsx` | 快捷按钮 | ✅ |
| `frontend/src/components/home/WorkbenchSummary.jsx` | 统计卡片行 | ✅ |
| `frontend/src/components/home/HomeSection.jsx` | 栏目标题包装 | ✅ |
| `frontend/src/hooks/useWorkbenchData.js` | 聚合拉取与轮询 | ✅ |
| `frontend/src/hooks/useHumanGates.js` | 人工卡点聚合（Workflow + Flow） | ✅ |
| `frontend/src/components/flows/HumanGatesPanel.jsx` | 卡点列表面板 | ✅ |

### 1.4 待办数据模型（前端统一）

```typescript
// 概念类型，可用 JSDoc 注释
type TodoItem = {
  id: string;
  kind: 'flow_human_gate' | 'workflow_human_gate' | 'manual_qc' | 'curation_batch';
  title: string;
  subtitle?: string;
  status: 'waiting_human' | 'pending' | 'running';
  href: string;          // deep link
  created_at?: string;
  meta?: Record<string, unknown>;
};
```

### 1.5 后端 API（需新增/扩展）

| 方法 | 路径 | 说明 | 优先级 |
|------|------|------|--------|
| GET | `/api/workbench/todos` | 聚合待办 | **P0** |
| GET | `/api/workbench/summary` | 计数：待办数、运行中 Flow、活跃查询 | **P0** |
| GET | `/api/flows/runs?status=waiting_human&limit=20` | Catalog Flow 运行中卡点 | **P0**（可先内存+文件，与 demo run 对齐） |
| GET | `/api/flows/list` | Catalog 中可用 Flow id 列表 | P1（U3 共用） |

**`/api/workbench/todos` 聚合来源（实现顺序）**

- [x] `forge_db`：`workflow_run.status = waiting_human`（现有 `WorkflowsPage` 已用）
- [x] `_demo_flow_runs` / 未来 flow run 持久化：`waiting_human`
- [x] manual_qc：未完成批次（`list_manual_qc_pending_groups` → `/manual-qc`）
- [x] curation：待上传 COCO 批次（`list_curation_action_batches` → `/curation?id=`）

**建议实现位置**：`server/routes/workbench.py` + 在 `app.py` 注册 blueprint。

### 1.6 复用现有组件

| 现有 | 用法 |
|------|------|
| `QueryJobsContext` | `RecentQueriesPanel` 读 `jobs` |
| `QueryJobsTray` | U1 完成后可改为调用同一数据源，或 Home 显示摘要、Tray 显示详情 |
| `WorkflowsPage` 中 `waiting_human` 过滤逻辑 | 抽到 `hooks/useHumanGates.js` 供 Home + Flows 共用 ✅ |
| `DemoFlowPage` → `StepTimeline` | 抽到 `components/flows/StepTimeline.jsx` |

### 1.7 Home 线框（结构）

```text
┌─ HomePage ─────────────────────────────────────────────┐
│ PageHeader: 工作台                    [角色: 质检员 ▾]   │
├────────────────────────────────────────────────────────┤
│ QuickActions: [新建查询] [同步 Catalog] [编排演示]      │
├──────────────┬─────────────────┬───────────────────────┤
│ TodoList     │ ActiveFlows     │ RecentQueries         │
│ (主列 40%)   │ (30%)           │ (30%)                 │
└──────────────┴─────────────────┴───────────────────────┘
```

### 1.8 U1 验收标准

- [x] 登录后默认进入 `/` 工作台（或配置可改回 `/query`）
- [x] 存在 `waiting_human` 的 workflow run 时，待办列表可见且点击跳到业务页
- [x] 进行中的查询任务在「最近查询」实时更新（与 Tray 一致）
- [x] 空状态有引导文案（「暂无待办，去查询」）
- [x] 移动端 1280px 以下三栏变单栏堆叠（`panel-grid-3`）
- [x] `useHumanGates` 抽到 hooks 供 Flows 页共用

---

## U2 — 四层导航 + 场景 Hub

### 2.1 目标

侧栏从 15+ 平铺项改为 **4 个一级域**；域内用已有 `SceneHubNav` 切换。

### 2.2 信息架构映射

| 一级 | 路由前缀 | 包含页面 |
|------|----------|----------|
| **工作台** | `/` | Home（U1） |
| **作业** | `/work/*` 或保持扁平路径 | 查询、结果、历史、策略、质检、归档、预测、任务、模型 |
| **流水线** | `/flows/*` | Flow 目录、运行记录、演示（U3 合并） |
| **平台** | `/platform/*` | 工具箱、训练平台、图库、手册、设置 |

**推荐：路径保持扁平，仅改导航分组**（改动最小）

```text
Layout.jsx navGroups:
  workbench → /
  work      → /query, /query-results, /history, /strategies,
              /manual-qc, /curation,
              /online-predict, /jobs, /models
  flows     → /flows, /flows/runs, /demo（/demo 可 redirect）
  platform  → /toolbox, /training, /viewer, /docs, /config
```

### 2.3 新建/修改文件

| 文件 | 改动 |
|------|------|
| `frontend/src/components/Layout.jsx` | 分组导航；顶栏可选 4-tab |
| `frontend/src/components/AppTopNav.jsx` | **新建**：一级 Tab + 待办徽章 |
| `frontend/src/components/SceneHubNav.jsx` | 扩展 `workflows`、`platform` variant（可选） |
| `frontend/src/config/nav.js` | **新建**：导航配置单源（id、path、icon、group、roles） |

### 2.4 `nav.js` 配置示例

```javascript
export const NAV_GROUPS = [
  { id: 'workbench', label: '工作台', items: [{ to: '/', label: '概览', end: true }] },
  { id: 'work', label: '作业', hub: 'query', items: [/* ... */] },
  { id: 'flows', label: '流水线', items: [/* ... */] },
  { id: 'platform', label: '平台', items: [/* ... */] },
];
```

### 2.5 路由调整

| 路径 | 动作 |
|------|------|
| `/workflows` | U3 重定向到 `/flows` 或保留 alias |
| `/demo` | 合并进 `/flows/demo`（可选） |

### 2.6 U2 验收标准

- [x] 侧栏仅显示 4 个分组标题 + 当前组子项（顶栏选组切换）
- [x] 查询相关页顶栏仍有 `SceneHubNav`（query variant；`/query` 入口已修正）
- [x] 质检页有 qc variant；预测页有 predict variant
- [x] 全局待办数显示在顶栏（读 U1 summary API）
- [x] 折叠侧栏行为与现有一致
- [x] `config/nav.js` 单源 + L1/L2 `UserPrefsContext` 过滤

---

## U3 — 流水线页（Catalog 只读）

### 3.1 目标

编排 UI **只读 Catalog + 触发运行 + 看时间线**；弱化自研 DAG 编辑。

### 3.2 路由

| 路径 | 页面 | 说明 |
|------|------|------|
| `/flows` | `FlowsCatalogPage` | Flow 卡片列表（releases + pipelines） |
| `/flows/runs` | `FlowRunsPage` | Kestra 执行历史（外链或 API 镜像） |
| `/flows/runs/:id` | `FlowRunDetailPage` | 步骤时间线 + resume |
| `/flows/demo` | 迁自 `DemoFlowPage` | 演示 |
| `/workflows` | `<Navigate to="/flows/runs" />` | 兼容 |

### 3.3 新建文件

| 文件 | 职责 | 状态 |
|------|------|------|
| `pages/FlowsCatalogPage.jsx` | 读 catalog pipelines + releases | ✅ |
| `pages/FlowRunsPage.jsx` | 运行列表 + 状态筛选 | ✅ |
| `pages/FlowRunDetailPage.jsx` | 详情 + StepTimeline + 继续 | ✅ |
| `pages/WorkflowsRedirect.jsx` | `/workflows` 兼容重定向 | ✅ |
| `components/flows/FlowCard.jsx` | 卡片：id、label、version、最近运行 | ✅ |
| `components/flows/StepTimeline.jsx` | 从 DemoFlowPage 抽出 | ✅ |
| `components/flows/FlowParamsForm.jsx` | 复用 WorkflowParamsForm | ✅ |
| `components/flows/PipelineYamlDrawer.jsx` | 只读 YAML 抽屉 | ✅ |
| `server/services/flows.py` | Catalog / Runs 聚合 API 逻辑 | ✅ |

### 3.4 API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/catalog/status` | 已有 |
| GET | `/api/flows/list` | pipeline id、label、path、version |
| GET | `/api/flows/releases` | 解析 `releases.yaml` |
| POST | `/api/flows/run` | 已有 |
| GET | `/api/flows/runs` | 运行列表（需持久化或合并 forge runs） |
| GET | `/api/flows/runs/:id` | 运行详情 |
| POST | `/api/flows/runs/:id/resume` | 已有 demo resume 逻辑扩展 |

### 3.5 WorkflowsPage 迁移策略

| 功能 | 处理 |
|------|------|
| DAG 编辑器 | 标记 **deprecated**，隐藏入口或移到「高级 / 遗留」 |
| 模板组合 launch | 改为 Catalog Flow 卡片「运行」 |
| Agent 草稿 | 移到 Platform 或 Flows 页「开发者」折叠区 |
| Schedules | **Kestra** Cron（Edge + Hub）；IISP 只读展示/外链 Kestra UI |
| Notifications | 保留在 FlowRuns 详情侧边 |

### 3.6 U3 验收标准

- [x] `/flows` 列出 `catalog_cache/pipelines/` 下 Flow（至少 demo + legacy）
- [x] 可从 UI 触发 `welcome_demo` 并看到步骤时间线
- [x] `waiting_human` 在列表和详情高亮，可 resume
- [x] 可查看 Pipeline YAML（只读），无「保存到 DB 模板」主路径
- [x] 旧 `/workflows` 书签不 404（redirect → `/flows/runs`）

---

## U4 — 工具箱分层 + 统一状态

### 4.1 目标

工具箱对业务用户友好；开发者功能折叠；全站状态 pill 一致。

### 4.2 文件

| 文件 | 改动 | 状态 |
|------|------|------|
| `pages/ToolboxPage.jsx` | 拆 Tab：`browse` / `developer` | ✅ |
| `components/toolbox/ToolCard.jsx` | **新建** | ✅ |
| `components/toolbox/ToolDetailPanel.jsx` | **新建** | ✅ |
| `components/ui/StatusPill.jsx` | **新建**（从 WorkflowsPage 抽离） | ✅ |
| `styles/status.css` | **新建**：`.status-pill--running` 等 | ✅ |

### 4.3 StatusPill 统一映射

```javascript
export const STATUS_MAP = {
  pending: { label: '排队', tone: 'neutral' },
  running: { label: '运行中', tone: 'info' },
  waiting_human: { label: '待人工', tone: 'warn' },
  done: { label: '完成', tone: 'success' },
  failed: { label: '失败', tone: 'danger' },
  skipped: { label: '跳过', tone: 'neutral' },
  canceled: { label: '已取消', tone: 'neutral' },
};
```

**替换 inline 颜色的页面**：`StepTimeline` / Flow Runs ✅、`WorkflowsPage` ✅、`JobsList` ✅、Query Tray / Home 最近查询 ✅；`HistoryPage` 保留 SnapshotDot（无运行态字段）

### 4.4 Toolbox 用户层字段

| 字段 | 来源 |
|------|------|
| 名称 | `manifest.label` |
| 说明 | `manifest.description` |
| 场景标签 | `manifest.tags` 或 `kind` |
| 使用次数 | `toolStats` API |

### 4.5 U4 验收标准

- [x] 工具箱默认 Tab 为卡片浏览，无 JSON 编辑器
- [x] 「开发者」Tab 含：JSON 试运行、Catalog sync log、Manifest 信息
- [x] Query / Flow / Job 列表使用同一 `StatusPill`
- [x] Catalog 同步按钮在 Platform 区仍可达（Toolbox 开发者 Tab 保留）

---

## U5 — 设计系统 + Command Palette + 角色

### 5.1 tokens 抽取

| 文件 | 动作 | 状态 |
|------|------|------|
| `frontend/src/styles/tokens.css` | 从 `app.css` :root 抽出 | ✅ |
| `frontend/src/styles/app.css` | `@import './tokens.css'` | ✅ |
| `packages/detunify/.../tokens.css` | 文档注明与主壳对齐（可选 CI diff） | ⬜ |

### 5.2 布局类（减少 inline style）

| 类名 | 用途 |
|------|------|
| `.page-header` | 标题 + 描述 + 操作区 |
| `.split-layout` | 左列表 + 右详情 |
| `.panel-grid-3` | Home 三栏 |
| `.empty-state` | 空列表引导 |

### 5.3 Command Palette

| 文件 | 职责 | 状态 |
|------|------|------|
| `components/CommandPalette.jsx` | ⌘K / Ctrl+K | ✅ |
| `hooks/useCommandPalette.js` | 注册命令 | ✅ |
| `config/commands.js` | 静态命令：跳转、同步 Catalog、跑 demo | ✅ |

依赖：`cmdk` 或自研 100 行 modal（优先轻量自研）。

### 5.4 两层角色视图（L1 / L2）

**依据**：[`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) §2 — 交付/客户质检 = L1；SA/算法/光学 = L2。

| 文件 | 职责 | 状态 |
|------|------|------|
| `context/UserPrefsContext.jsx` | `tier` · `persona` · `defaultHome` | ✅ |
| `config/personas.js` | persona 定义与默认首页 | ✅ |
| `config/nav.js` | 按 `tier` 过滤侧栏；L1 **无** 策略/工具箱/Catalog | ✅ |
| `components/TierRouteGuard.jsx` | L1 路由重定向 | ✅ |
| `components/settings/UserPrefsSettings.jsx` | 设置页界面与角色 | ✅ |

**L1 侧栏（operator）**

```text
工作台 | 作业（查询场景/质检/看图）| 我的任务
```

**L2 侧栏（configurer）**

```text
工作台 | 作业（含策略）| 流水线 | 平台
```

默认 landing：

| persona | tier | 首页 |
|---------|------|------|
| delivery | L1 | `/` |
| customer_qc | L1 | `/`（待办优先） |
| sa | L2 | `/flows` |
| algo | L2 | `/query` |
| optical | L2 | `/` 或设备状态页（规划） |

### 5.5 品牌统一

- [x] 侧栏品牌：**IISP** / **工业检测解决方案平台**（`config/brand.js` · `studio/brand.py`）
- [ ] `public/brand/` favicon 与文档一致
- [ ] `USER_GUIDE.md` 截图说明更新（文档任务，非阻塞）

### 5.6 U5 验收标准

- [x] ⌘K 可搜索并跳转到主要页面
- [x] L1 账户 **看不见** 策略编辑、工具箱、Pipeline 编排入口
- [x] L2 账户可见完整四域；切换 persona 仅影响默认首页与快捷操作
- [x] 新页面使用 layout 类（`split-layout` · `tokens.css`）
- [x] `/viz`、`/online-predict` iframe 页保留「返回 IISP」顶栏

---

## 跨阶段：全局任务条（可选，U1 后）

将 `QueryJobsTray` 演进为 **`GlobalTaskStrip`**：

| 项 | 说明 |
|----|------|
| 位置 | 主内容区底部固定 |
| 数据源 | Query jobs + 可选 Flow run progress |
| 行为 | 点击展开详情；完成 toast |

文件：`components/GlobalTaskStrip.jsx`，在 `Layout.jsx` 替换或包装 `QueryJobsTray`。

---

## 跨阶段：Deep link 约定

| 场景 | URL |
|------|-----|
| 归档待上传 | `/curation?batch={id}` |
| 人工质检 | `/manual-qc?batch={id}` |
| Flow 卡点 | `/flows/runs/{run_id}` |
| 查询结果 | `/query-results?task={task_id}` |
| 图库 | `/viewer?dataset=…` |

**待办 API 必须返回完整 `href`。**

---

## 测试清单

| 类型 | 内容 |
|------|------|
| 单元 | `StatusPill` 渲染；`nav.js` 角色过滤 |
| 集成 | `GET /api/workbench/todos` 聚合 |
| E2E（选手动） | Home 待办 → 跳转 curation → 完成后待办消失 |
| 回归 | `/query` 原查询流程；`/api/flows/run` demo |

---

## 建议实施顺序（单线程）

```text
Week 1:  U1 API + HomePage + StepTimeline 抽取
Week 2:  U2 Layout/nav.js + U4 StatusPill
Week 3:  U3 FlowsCatalog + FlowRuns + 弱化 WorkflowsPage
Week 4:  U5 tokens + CommandPalette + 角色 + 文档截图
```

可并行：**U2 与 U1**（不同文件）；**U4 StatusPill** 与 **U3** 并行。

---

## 不在本清单范围

- Electron / Tauri 桌面壳
- umi 迁移
- Kestra 内置 UI iframe 嵌入（仅外链）
- 完整 RBAC / 多租户
- 自研 Flow DAG 编辑器新功能

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.2 | 2026-06-09 | U2 四层导航落地：nav.js、AppTopNav、UserPrefs L1/L2 |
| v1.3 | 2026-06-09 | U1 组件拆分：home/* + useWorkbenchData |
| v1.4 | 2026-06-09 | U1 收尾：useHumanGates + HumanGatesPanel，Flows 页共用 |
| v1.5 | 2026-06-09 | U3 流水线：Catalog/Runs/Detail + flows API + 路由迁移 |
| v1.6 | 2026-06-09 | U4 StatusPill 统一 + 工具箱 browse/developer 分层 |
| v1.1 | 2026-06-09 | L1/L2 导航、Kestra Schedules |
| v1.0 | 2026-06-09 | U1–U5 首版 |
