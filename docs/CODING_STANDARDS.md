# IISP 编码规范与技术选型

**版本**：v1.2  
**日期**：2026-06-09  
**状态**：项目级强制约定 — Vibe Coding / 人工 PR 均须遵守  
**标准**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) v2.2 · [`DOCS_INDEX.md`](./DOCS_INDEX.md)

---

## 1. 适用范围

| 贡献类型 | 必读章节 |
|----------|----------|
| Vibe 新 Tool | §2–§4、§7、§9 |
| Vibe 新 Pipeline | §2、§5、§9 |
| 平台 Core 改动 | 全文 + Skill `iisp-platform-core` |
| 前端 Shell | §2、§6、§9 |
| PR 提交前 | §9、§10 |

---

## 2. 代码原则（不可违反）

### 2.1 架构原则

| # | 原则 | 含义 |
|---|------|------|
| P1 | **平台薄、工具厚** | 组合逻辑在 Catalog Pipeline，不在 Platform |
| P2 | **契约唯一** | 集成只通过 Tool Contract v1 + Pipeline YAML |
| P3 | **编排零 import** | Kestra / UI 不得 `import studio.*` 执行业务 |
| P4 | **Tool 不互引** | 禁止 Tool A import Tool B 的 `service.py` |
| P5 | **可序列化边界** | 跨步只传 JSON 与 artifact URI，不传 DataFrame/句柄 |
| P6 | **配置进 Git** | 策略与 Pipeline 权威在 `iisp-catalog`，不在 DB 模板 |
| P7 | **成熟框架优先** | 调度/队列/通知/鉴权/观测不重复造轮 |
| P8 | **AI 只写文件** | Agent 只改允许路径；运行态无 LLM 调度 |
| P9 | **最小 diff** | 不顺手重构、不扩大 PR 范围 |
| P10 | **可校验再合并** | 无 `validate` 通过不得 merge |

安全与 Token 详见 [`SECURITY.md`](./SECURITY.md)；平台遗漏见 [`PLATFORM_RISK_REGISTER.md`](./PLATFORM_RISK_REGISTER.md)。

### 2.2 允许改动的路径

```text
skills/**/*
tools/**/*
packages/<your-tool>/**     # 独立 Tool 包（过渡期）
capabilities/**             # 内置 Tool（过渡期）
iisp-catalog/**             # Pipeline / 策略（Catalog PR）
frontend/**                 # UI（须符合 §6）
tests/**                    # 对应测试
docs/**                     # 文档
```

### 2.3 禁止或需平台组审批

```text
studio/forge/workflow_engine.py      # 禁止扩展，终态删除
studio/forge/workflow_scheduler.py
server/core.py                       # 仅 Gateway 薄改动
orchestration/flow_runner.py         # 仅平台组
config.json / .config.key            # 禁止提交
```

---

## 3. 技术选型（定稿）

### 3.1 后端

| 项 | 选型 | 禁止/不推荐 |
|----|------|-------------|
| 语言 | Python 3.10+ | — |
| Web（现） | Flask | 新 Gateway 可用 FastAPI |
| 校验 | Pydantic v2 / JSON Schema | 手写 if 校验 params |
| 队列 | RQ + Redis（Edge）/ Celery（Hub） | 无限线程轮询 |
| ORM/SQL | 现有 MySQL 访问层 + `lib/platform/db` | 新 Tool 内嵌 SQL 硬编码连接串 |
| 编排（Edge + Hub） | **Kestra** | 自研 DAG、Windmill、cron 主编排 |
| 配置 | Git Catalog + Provider | DB workflow 模板 |
| Agent | Cursor Skills + MCP | 运行时 LLM 编排 |

### 3.2 前端

| 项 | 选型 | 禁止/不推荐 |
|----|------|-------------|
| 框架 | React 19 | umi、Next 迁移 |
| 构建 | Vite 6 | CRA |
| 路由 | React Router | — |
| 请求 | fetch（`api/client.js`） | 全仓强改 axios（可渐进） |
| 服务端状态 | TanStack Query（新页） | 每页自写轮询 |
| 样式 | CSS + CSS 变量（`tokens.css`） | 全仓强改 less |
| 表单 | RJSF（schema 驱动） | 手写大表单 |
| 桌面 | 浏览器 / kiosk | Electron |

### 3.3 工具与共建

| 项 | 选型 |
|----|------|
| Tool 契约 | `contract_version: v1` |
| Manifest | `tool.manifest.json` |
| 场景 Skill | `skills/<scene>/SKILL.md` |
| CLI | `./scripts/iisp` |
| CI | `iisp tool validate` / `iisp workflow validate` |

---

## 4. Python / Tool 编码规范

### 4.1 Tool 包结构（标准）

```text
tools/<tool_id>/
├── tool.manifest.json
├── invoke.py          # handle(body) -> dict，仅映射
├── service.py         # 业务逻辑，无 Flask
├── schemas/           # JSON Schema（可选）
├── tests/
│   └── test_invoke.py
└── README.md          # 可选，一行说明
```

### 4.2 invoke.py

```python
# 规范：
# - 函数名 handle 或模块约定 entry
# - 返回 status: done|failed|skipped|waiting_human|accepted
# - outputs 仅 JSON 可序列化类型
# - 不在此 import pandas 除非本 Tool 需要；不在模块顶层 import torch
```

**禁止**：

- 在 `invoke.py` 调用其他 Tool  
- 在 Gateway 注册表外新增 HTTP 路由执行业务  
- 返回 `DataFrame`、ORM 对象  

### 4.3 service.py

- 可依赖 `packages/platform`（db、img_path、sn_query）  
- 可依赖标准库 + 项目 `requirements.txt` 已有库  
- 新增重型依赖须在 Manifest 注明，并评估 Edge 内存  

### 4.4 Manifest

```json
{
  "id": "kebab-or-snake",
  "version": "semver",
  "label": "中文名",
  "contract_version": "v1",
  "runtime": "inprocess",
  "module": "tools.<id>.invoke:handle",
  "params_schema": { "type": "object", "properties": {}, "required": [] },
  "outputs": ["field_a"],
  "artifacts": ["csv"],
  "tags": ["query"]
}
```

- `id` 与 SKILL `name` 一致  
- `outputs` 字段名与 `invoke` 实际返回一致  

### 4.5 命名

| 类型 | 规则 | 示例 |
|------|------|------|
| tool id | 小写，`a-z0-9-` | `daily-trawl-query` |
| flow id | snake_case | `daily_ng_curation` |
| step id | snake_case | `export_coco` |
| Python 模块 | snake_case | `service.py` |

### 4.6 测试（强制）

**团队原则**：每实现一个功能，**必须与功能同一 PR** 交付单元测试。Skill：**iisp-unit-tests**；PR 审查：**iisp-review-pr** §3.0。

- 每个 Tool 至少：`test_invoke` 冒烟（mock 外部 DB 可选）  
- 每个新 API / Gateway 路由：Flask `test_client` 至少 happy path + 一处失败/边界  
- Bug 修复：先写复现测试再改代码  
- 不测试 obvious 恒真断言  
- 运行：`python -m pytest tests/ -q`（或本次改动路径）  

---

## 5. Pipeline YAML 规范

见 [`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) Part VII。

**强制**：

- 每个 `nodes[].tool` 必须已在 Registry  
- 使用 `{{params.*}}` / `{{steps.<id>.outputs.*}}`  
- 人工步骤写在 `notes`，含 `ui_url` 提示  
- 合并前：`./scripts/iisp workflow validate <path>`  

**禁止**：

- 在 YAML 内嵌 Python/SQL  
- 引用未注册 tool_id  
- 在 Platform DB 存等价模板作为权威  

---

## 6. 前端编码规范

### 6.1 原则

- 新页使用 `page-header`、`split-layout` 等布局类，避免大段 `style={{}}`  
- 状态展示用统一 `StatusPill`（见 UI 清单）  
- 长任务用 TanStack Query 或现有 Context，不复制轮询逻辑  
- 调用 Tool 走 `api/client.js`，不直连编排引擎内部 API  

### 6.2 目录

```text
frontend/src/
├── pages/           # 路由页
├── components/      # 复用组件
├── api/             # API 客户端
├── lib/             # 纯函数工具
├── context/         # React Context
└── styles/          # tokens.css + app.css
```

### 6.3 禁止

- 在前端实现 DAG 编辑器作为主路径  
- 把 Pipeline 权威定义 POST 到 workflow 模板 API（迁移期除外且 deprecated）  

---

## 7. Platform Core 编码规范（平台组）

- Gateway 单一路由：`/v1/tools/{id}/invoke`  
- 懒加载 Tool：`importlib` 首次 invoke  
- 单 worker 生产默认；重活子进程  
- OpenAPI 与 Manifest 同步生成  
- 新增 Core 功能需更新 `IISP_DESIGN_FINAL.md` 并 CODEOWNERS 审批  

Skill：`.cursor/skills/iisp-platform-core/SKILL.md`

---

## 8. Git 与 PR

### 8.1 分支

- `feat/<tool-id>` / `feat/<flow-id>` / `fix/...`  

### 8.2 Commit

- 中文或英文均可；一句说清 **why**  
- 不 commit：`config.json`、密钥、大二进制、`exports/`  

### 8.3 PR 描述模板

```markdown
## 类型
- [ ] 新 Tool  - [ ] 新 Pipeline  - [ ] 平台 Core  - [ ] UI  - [ ] 文档

## 说明
（意图与行为）

## 校验
- [ ] iisp tool validate …
- [ ] iisp workflow validate …
- [ ] pytest …

## 解耦自检
- [ ] 未 import 其他 Tool service
- [ ] 未改 workflow_engine/scheduler
- [ ] 未在 Gateway 写组合逻辑

## 变更记录
- [ ] 已更新 `docs/PLATFORM_CHANGELOG.md` [Unreleased]（或注明无用户可见变更）
- [ ] 已同步 PRODUCT_DESIGN / releases.yaml / USER_GUIDE 等（见 PLATFORM_CHANGELOG 映射表）
```

---

## 9. 提交前 Checklist（Agent 与人工）

```bash
# Tool
./scripts/iisp tool validate path/to/tool.manifest.json
python -m pytest tools/<id>/tests/ -q

# Pipeline
./scripts/iisp workflow validate iisp-catalog/pipelines/.../foo.yaml

# 全仓回归（平台组）
python -m pytest tests/ -q
```

Skill：`.cursor/skills/iisp-review-pr/SKILL.md`

---

## 10. 反模式速查

| 反模式 | 正确做法 |
|--------|----------|
| 功能改了不写 changelog | **iisp-record-platform-change** + 同 PR 更新 `PLATFORM_CHANGELOG.md` |
| 在 `workflow_engine` 加新步骤 handler | 新 Tool + Pipeline YAML |
| Tool A 调 Tool B | Pipeline 串联 + invoke |
| 编排 Flow 里写 Python | YAML + Kestra HTTP |
| Agent 改 `server/core` 加组合 | Catalog PR |
| 前端轮询每页一套 | TanStack Query / 共享 Tray |
| 传 CSV 内容跨步 | 传 `task_id` + artifact URI |
| Edge 用 cron 代替 Kestra | **Edge 也部署 Kestra**（单机） |

---

## 11. 文档与 Skill 索引

| 资源 | 路径 |
|------|------|
| 平台 changelog | `docs/PLATFORM_CHANGELOG.md` |
| 最终架构 | `docs/IISP_DESIGN_FINAL.md` |
| 产品设计 | `docs/PRODUCT_DESIGN.md` |
| 架构图 | `docs/ARCHITECTURE_DIAGRAMS.md` |
| 项目 Skills | `.cursor/skills/README.md` |
| Cursor Rules | `.cursor/rules/` |

---

## 12. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.2 | 2026-06-09 | PLATFORM_CHANGELOG、变更记录 PR 模板 |
| v1.1 | 2026-06-09 | Kestra 唯一编排、DOCS_INDEX |
| v1.0 | 2026-06-09 | 首版 |
