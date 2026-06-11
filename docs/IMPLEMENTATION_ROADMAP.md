# IISP 实施路线图（可执行清单）

**更新**：2026-06-09 · **权威架构**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) Part XV

> 本文是**单一待办入口**：把 M/U/S/A 阶段、近期 sprint 与验收标准集中在一处。  
> 详细 UI checklist 见 [`UI_REDESIGN_CHECKLIST.md`](./UI_REDESIGN_CHECKLIST.md)；编排细则见 [`TOOLBOX_ORCHESTRATION.md`](./TOOLBOX_ORCHESTRATION.md)。

---

## 状态图例

| 标记 | 含义 |
|------|------|
| ✅ | 已交付 |
| 🚧 | 进行中 / 部分交付 |
| ⬜ | 未开始 |

---

## 近期 Sprint（优先）

| ID | 交付 | 状态 | 验收 |
|----|------|------|------|
| **M1-gw** | `POST /v1/tools/{id}/invoke` Contract v1 | ✅ | `pytest tests/test_gateway_workbench.py`；Kestra HTTP 可调 |
| **M2-kestra** | Kestra 部署（Docker + **原生一体包**） | ✅ | compose 或 `platform-start.sh`；UI 见 `iisp.daily_ng_curation` |
| **M2-pack** | `platform-pack.sh` 分发 tar.gz（含 Kestra vendor） | ✅ | `packaging/dist/iisp-platform-*.tar.gz` |
| **M2-run** | 手动跑通 `daily_ng_curation`（含 Pause） | ✅ | `daily_ng_pause_resume_e2e.sh`；smoke Flow + Resume 全链路 |
| **U1-api** | `GET /api/workbench/todos` + `/summary` | ✅ | API 返回聚合待办 |
| **U1-ui** | `HomePage` 组件拆分 + 默认 `/` | ✅ | `components/home/*` + `useWorkbenchData` |
| **U2-nav** | 四层导航 + `nav.js` + `AppTopNav` | ✅ | 顶栏四域 + L1/L2 视图切换 + persona |
| **test-policy** | **iisp-unit-tests** 团队强制同 PR 测试 | ✅ | Skill + Rule + review-pr |
| **P2-pack** | `iisp skill pack` CLI | ✅ | `skill validate` / `skill pack` / `flow list-kestra` |
| **U3-flows** | 流水线只读页 + `GET /api/flows/list` | ✅ | `/flows` + workbench API |
| **M3-toolhost** | ToolHost + integration API；query/viz/unify 三态集成 | ✅ | `pytest tests/test_tool_integration.py tests/test_query_*.py -q`；`curl /api/tools/query/integration` |
| **F1-kestra-run** | Shell 触发 Kestra Flow（`/flows` 填参运行） | ✅ | `pytest tests/test_kestra_flow_execute.py -q` |
| **F3-notify-ui** | 设置页 `workflow_notify` 表单 | ⬜ | 见 [`FLOW_UI_CONFIG_ROADMAP.md`](./FLOW_UI_CONFIG_ROADMAP.md) F3 |

---

## 平台迁移 M0–M5

| 阶段 | 交付 | 状态 |
|------|------|------|
| **M0** | Registry、Catalog sync、flow run demo | ✅ |
| **M1** | `/v1` Gateway、OpenAPI、RQ | 🚧 Gateway ✅；OpenAPI/RQ ⬜ |
| **M2** | Kestra 生产 Flow、Resume API | ✅ compose ✅；编排 e2e ✅；Pause→Resume 全链路 ✅ |
| **M3-query** | query 单工具 + REST 代理 + COCO 式 UI 挂载 `/tools/query` | ✅ | `bash tools/query/ui/build.sh`；`pytest tests/test_query_mount.py` |
| **M3-toolhost** | 通用 ToolHost + `GET /api/tools/<id>/integration`；VizToolHost / UnifyToolHost | ✅ | `pytest tests/test_tool_integration.py -q` |
| **M3** | tools/ 标准包、UI 工作台 | 🚧 U1 工作台 ✅；query 工具 ✅；ToolHost ✅ |
| **M4** | 删 workflow_engine/scheduler | ⬜ |
| **M5** | .iisp-tool、OIDC、Metabase | ⬜ |

---

## 前端 U1–U5

| 阶段 | 主题 | 状态 |
|------|------|------|
| **U1** | 工作台 + 待办聚合 | ✅ |
| **U2** | L1/L2 分层导航 | ✅ |
| **U3** | 流水线 Catalog 只读 | ✅ |
| **U4** | 工具箱分层 | ✅ |
| **U5** | Command Palette + 角色视图 | ✅ |

---

## 组合模块 Kestra 模板（L2 共建）

| 模板 | Flow id | 状态 |
|------|---------|------|
| 数据收集闭环 | `daily_ng_curation` | ✅ YAML |
| 召回测评 | `recall_eval` | ⬜ |
| 误检率评测 | `fpr_eval` | ⬜ |

---

## 本地验证命令

```bash
# Gateway
python -m pytest tests/test_gateway_workbench.py -q

# 原生一体启动（IISP + Kestra + MySQL kestra 库）
bash deploy/scripts/platform-start.sh
bash deploy/scripts/kestra_e2e_smoke.sh

# 或 Docker 开发路径
cd deploy && docker-compose -f docker-compose.kestra.yml up -d

# 打包
bash deploy/scripts/platform-pack.sh

# 工作台 API
curl -s http://127.0.0.1:5050/api/workbench/summary | jq

# 工具集成 status
curl -s http://127.0.0.1:5050/api/tools/query/integration | jq
curl -s http://127.0.0.1:5050/api/tools/viz/integration | jq

# Query / ToolHost 测试
python -m pytest tests/test_tool_integration.py tests/test_query_tools.py tests/test_query_rest_proxy.py -q
cd frontend && npm test -- --run src/lib/toolIntegration.test.js src/lib/vizIframe.test.js
```

---

## 修订记录

| 日期 | 说明 |
|------|------|
| 2026-06-09 | 初版：M1 Gateway、M2 compose、U1 工作台 |
| 2026-06-09 | M2-pack：原生 `platform-start/stop/pack` + MySQL `kestra` 库 |
| 2026-06-09 | M3-toolhost：ToolHost 框架 + query/viz/unify integration API |
| 2026-06-09 | FLOW_UI_CONFIG_ROADMAP：界面可配编排分阶段清单 |
