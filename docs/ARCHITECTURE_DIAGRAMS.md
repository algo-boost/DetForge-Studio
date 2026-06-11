# IISP 技术架构图集

**版本**：v1.3  
**日期**：2026-06-09  
**标准**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) **v2.2** · [`DOCS_INDEX.md`](./DOCS_INDEX.md)

> 实现细节以设计定稿为准。编排：**Kestra 唯一**（Edge + Hub）。

---

## 1. C4 上下文（系统与外部）

```mermaid
C4Context
  title IISP 系统上下文

  Person(l1, "L1 交付/质检", "待办、查询场景、审图")
  Person(l2, "L2 SA/算法/光学", "策略、Kestra Flow、Tool 共建")
  Person(ops, "运维 SRE", "Kestra、Catalog sync")
  Person(vibe, "Agent 贡献者", "Skill/Tool/Pipeline PR")

  System(iisp, "IISP Platform", "Tool Gateway + Shell + Catalog Client")
  System_Ext(kestra, "Kestra", "唯一编排 Edge+Hub")
  System_Ext(git, "Git iisp-catalog", "策略 + pipelines/kestra")
  System_Ext(mf, "Magic-Fox", "训练平台")
  System_Ext(vb, "vision_backend", "产线库")
  System_Ext(feishu, "飞书多维表格", "指标看板")
  System_Ext(n8n, "n8n", "通知旁路")
  System_Ext(agent, "Coding Agent + MCP", "设计态 Cursor/Claude/Codex/OpenClaw")

  Rel(l1, iisp, "浏览器")
  Rel(l2, iisp, "浏览器")
  Rel(ops, iisp, "管理")
  Rel(vibe, agent, "Vibe Coding")
  Rel(agent, git, "PR")
  Rel(iisp, git, "catalog sync")
  Rel(kestra, iisp, "HTTP invoke")
  Rel(iisp, vb, "查询")
  Rel(iisp, mf, "同步")
  Rel(kestra, feishu, "metrics sync Tool")
  Rel(n8n, kestra, "Webhook 通知")
```

---

## 2. C4 容器（部署单元）

```mermaid
flowchart TB
  subgraph clients [客户端]
    Browser[浏览器 React Shell]
    AgentIDE[Coding Agent]
  end

  subgraph edge [Edge 节点]
    IISP_E[IISP :5050]
    Kestra_E[Kestra 单机]
    MySQL_E[(MySQL)]
  end

  subgraph hub [Hub 节点]
    IISP_H[IISP Gateway]
    Kestra_H[Kestra + PG]
    Redis_H[(Redis)]
    MySQL_H[(MySQL)]
  end

  subgraph git [配置]
    Catalog[iisp-catalog Git]
  end

  subgraph embed [子应用 可选]
    Viz[COCOVisualizer /viz]
    Unify[DetUnify /unify]
  end

  Browser --> IISP_E
  Browser --> IISP_H
  Browser --> Viz
  Browser --> Unify
  AgentIDE -->|MCP dev| IISP_H
  Kestra_E -->|invoke| IISP_E
  Kestra_H -->|invoke| IISP_H
  IISP_E --> MySQL_E
  IISP_H --> Redis_H
  IISP_H --> MySQL_H
  Catalog -->|sync| IISP_E
  Catalog -->|sync| IISP_H
  Kestra_E -->|git sync pipelines/kestra| Catalog
  Kestra_H -->|git sync pipelines/kestra| Catalog
```

---

## 3. 逻辑分层

```mermaid
flowchart TB
  subgraph L5 [L5 设计态]
    AgentNode[Agent + Skills agent/skills]
    MCP[MCP Server]
  end

  subgraph L4 [L4 配置 Catalog]
    Strat[strategies]
    Pipe[pipelines/kestra]
    Rel[releases]
  end

  subgraph L3 [L3 编排 Kestra]
    K_E[Kestra Edge]
    K_H[Kestra Hub]
  end

  subgraph L2 [L2 契约 Contract]
    GW[Tool Gateway /v1]
    OAS[OpenAPI]
  end

  subgraph L1 [L1 工具 Tools]
    T1[query]
    T2[manual-qc]
    T3[curation]
    TN[...]
  end

  subgraph L0 [L0 数据 Data]
    VB[(vision_backend)]
    DF[(detforge)]
    FS[exports/artifacts]
  end

  AgentNode --> MCP
  AgentNode -->|PR| L4
  L4 --> L3
  K_E --> GW
  K_H --> GW
  GW --> OAS
  GW --> T1 & T2 & T3 & TN
  T1 --> VB
  T2 & T3 --> DF
  T3 --> FS
```

---

## 4. Tool 调用序列（Kestra）

```mermaid
sequenceDiagram
  participant K as Kestra
  participant G as IISP Gateway
  participant R as Registry
  participant T as Tool invoke
  participant D as detforge / VB

  K->>G: POST /v1/tools/query/invoke
  G->>R: resolve query
  R->>T: handle(params)
  T->>D: 业务查询
  D-->>T: rows / task_id
  T-->>G: status done + outputs
  G-->>K: JSON response
  K->>G: POST /v1/tools/curation-export/invoke
  Note over K,G: params 含上游 outputs
```

---

## 5. 人工卡点序列

```mermaid
sequenceDiagram
  participant K as Kestra
  participant G as Gateway
  participant U as 用户 UI L1
  participant R as Resume API

  K->>G: invoke export
  G-->>K: done batch_id
  K->>G: invoke gate-human
  G-->>K: waiting_human
  K->>K: Pause
  U->>U: /curation 上传 COCO
  U->>R: POST /v1/orchestration/resume
  R->>K: resume execution
  K->>G: invoke import
  G-->>K: done
```

---

## 6. Vibe Coding 设计态

```mermaid
flowchart LR
  subgraph l2 [L2 配置者]
    NL[自然语言]
  end

  subgraph ide [任意 Coding Agent]
    SK[iisp-skill-author / compose-flow]
    AG[Agent]
    NL --> AG
    SK --> AG
  end

  subgraph mcp [MCP]
    LT[list_tools]
    VP[validate_pipeline]
    VM[validate_manifest]
  end

  subgraph out [产出]
    SKILL[skills/SKILL.md]
    TOOL[tools/*]
    YAML[pipelines/kestra/*.yaml]
  end

  subgraph gate [门禁]
    V[CLI validate]
    CI[GitHub CI]
  end

  AG --> mcp
  AG --> out
  out --> V --> CI
  CI -->|merge + Kestra sync| RUN[运行态 Kestra 无 LLM]
```

---

## 7. Catalog 数据流

```mermaid
flowchart LR
  GH[GitHub / 内网 Git]
  PR[PR + CODEOWNERS]
  Sync[iisp catalog sync]
  Cache[catalog_cache]
  Strat[strategies 加载]
  Kestra[Kestra git sync]

  GH --> PR --> GH
  GH --> Sync --> Cache
  Cache --> Strat
  GH --> Kestra
```

---

## 8. 前端与 L1/L2 导航（目标）

```mermaid
flowchart TB
  Shell[App Shell]
  subgraph L1 [L1 operator]
    Home[工作台/待办]
    Work[作业/场景]
    Tasks[我的任务]
  end
  subgraph L2 [L2 configurer]
    Flows[流水线 + Kestra 外链]
    Plat[工具箱/策略/Catalog]
  end

  Shell --> Home & Work & Tasks
  Shell --> Flows & Plat
  Home --> API[api/client.js]
  Flows --> API
  API --> GW[Flask /v1]
```

---

## 9. 仓库模块依赖（解耦）

```mermaid
flowchart TB
  subgraph allowed [允许依赖]
    Platform[lib/platform]
    Tools[tools/*]
    Cap[capabilities 过渡期]
  end

  subgraph forbidden [禁止]
    Engine[workflow_engine]
    Cross[Tool A → Tool B service]
  end

  Orch[Kestra/UI] -->|HTTP only| GW[Gateway]
  GW --> Tools
  GW --> Cap
  Tools --> Platform
  Cap --> Platform

  Engine -.->|终态删除| X[❌]
  Cross -.-> X
```

---

## 10. 演进路线图

```mermaid
gantt
  title IISP 演进
  dateFormat YYYY-MM
  section 平台 M
  M0 Registry Catalog demo   :done, m0, 2026-05, 2026-06
  M1 v1 Gateway OpenAPI RQ   :m1, 2026-06, 2026-07
  M2 Kestra Edge+Hub 生产    :m2, after m1, 2026-08
  M3 tools 标准包 UI 工作台   :m3, after m2, 2026-09
  M4 删 workflow_engine      :m4, after m3, 2026-10
  section Agent A
  A1 Skills Rules 文档       :done, a1, 2026-06, 2026-06
  A2 agent context           :a2, 2026-06, 2026-07
  A3 validate 加强           :a3, after a2, 2026-07
  A4 MCP Server              :a4, after a3, 2026-07
  section UI U
  U1 工作台 L1/L2            :u1, 2026-06, 2026-07
  U2 分层导航                :u2, after u1, 2026-07
  U3 流水线 Kestra 观测      :u3, after u2, 2026-08
```

---

## 11. Deploy 模块依赖（原生一体包）

> 详述：[`deploy/README-native.md`](../deploy/README-native.md) · 实现：`orchestration/native/` · CLI：`cli/deploy_cmds.py`

### 11.1 分层与运行时

```mermaid
flowchart TB
  subgraph entry [L0 入口 — 无业务逻辑]
    SH_START[platform-start.sh]
    SH_STOP[platform-stop.sh]
    SH_STATUS[platform-status.sh]
    SH_FETCH[fetch_kestra.sh]
    SH_PACK[platform-pack.sh]
    CLI_MAIN["python -m cli.main deploy"]
    DEPLOY_CMDS[cli/deploy_cmds.py]
  end

  subgraph artifacts [L1 制品 deploy/]
    ENV[native/env.defaults]
    TPL[native/kestra-application.template.yml]
    COMPOSE[docker-compose.kestra.yml]
    SMOKE[scripts/kestra_*_smoke.sh]
    VENDOR[vendor/ kestra + plugins]
    RUNTIME[runtime/ pid · log · storage]
    GEN_YML[runtime/kestra-application.yml]
  end

  subgraph native [L2 编排域 orchestration/native/]
    PATHS[paths.py]
    DEF[defaults.py]
    MYSQL_SET[mysql_settings.py]
    BOOT[bootstrap.py]
    RENDER[config_render.py]
    PROC[process_manager.py]
  end

  subgraph platform [L3 平台运行时 — 与部署启动解耦]
    KC[orchestration/kestra_client.py]
    RESUME[server/routes/orchestration.py]
    WB[server/services/workbench.py]
    APP[app.py IISP :5050]
  end

  subgraph catalog [L4 配置源]
    FLOWS[iisp-catalog/pipelines/kestra/]
  end

  subgraph external [外部]
    CFG[config.json + .config.key]
    MY[(MySQL 同实例 kestra 库)]
    JAVA[Java 21+]
    DOCKER[Docker 可选]
  end

  SH_START & SH_STOP & SH_STATUS --> CLI_MAIN --> DEPLOY_CMDS
  SH_FETCH --> DOCKER
  SH_FETCH --> VENDOR
  SH_PACK --> SH_FETCH

  DEPLOY_CMDS --> BOOT & RENDER & PROC
  BOOT --> MYSQL_SET
  RENDER --> MYSQL_SET & DEF & TPL & PATHS
  PROC --> DEF & PATHS & VENDOR & RUNTIME
  DEF --> ENV
  MYSQL_SET --> CFG
  RENDER --> GEN_YML

  PROC -->|subprocess| KESTRA[Kestra :8080]
  PROC -->|subprocess| APP
  BOOT --> MY
  KESTRA --> GEN_YML & FLOWS & VENDOR
  KESTRA -->|HTTP invoke| APP

  KC -->|Resume / 查询 PAUSED| KESTRA
  RESUME --> KC
  WB --> KC

  COMPOSE -.->|Docker 开发路径| KESTRA
  SMOKE -.-> KESTRA & APP

  JAVA --> KESTRA
```

**依赖原则**：

| 规则 | 说明 |
|------|------|
| Shell 不堆业务 | `platform-*.sh` 仅转调 `iisp deploy` |
| 部署 ≠ 运行时客户端 | `process_manager` 管启停；`kestra_client` 管 API（Resume/待办） |
| MySQL 单一解析 | `mysql_settings.py` 读 `config.json`，bootstrap 与 render 共用 |
| 制品与代码分离 | 模板/env 在 `deploy/native/`；逻辑在 `orchestration/native/` |

### 11.2 `orchestration/native/` 模块内依赖

```mermaid
flowchart LR
  subgraph libs [平台 lib]
    STUDIO_PATHS[studio.paths APP_ROOT]
    LOAD_CFG[server.core.load_config]
  end

  PATHS[paths.py] --> STUDIO_PATHS
  DEF[defaults.py] --> PATHS
  MYSQL[mysql_settings.py] --> LOAD_CFG
  BOOT[bootstrap.py] --> MYSQL
  RENDER[config_render.py] --> MYSQL & DEF & PATHS
  PROC[process_manager.py] --> DEF & PATHS & STUDIO_PATHS

  DEPLOY_CMDS[cli/deploy_cmds.py] --> BOOT & RENDER & PROC & DEF
```

### 11.3 两条部署路径对比

```mermaid
flowchart TB
  subgraph native_path [原生一体包 推荐]
    N1[iisp deploy start]
    N2[MySQL kestra 库]
    N3[vendor/kestra JAR]
    N1 --> N2 & N3
  end

  subgraph docker_path [Docker Compose 本地开发]
    D1[docker-compose.kestra.yml]
    D2[内置 Postgres]
    D3[kestra/kestra 镜像]
    D1 --> D2 & D3
  end

  FLOWS[iisp-catalog/pipelines/kestra/]
  IISP[IISP :5050 Gateway]

  N3 --> FLOWS
  D3 --> FLOWS
  N3 & D3 -->|invoke| IISP
```

---

## 12. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.2 | 2026-06-09 | §11 Deploy 模块分层与依赖图（原生 + Docker 双路径） |
| v1.3 | 2026-06-09 | 设计态 Agent 去 Cursor 化；C4/§6 改为任意 Coding Agent + `agent/` |
| v1.1 | 2026-06-09 | Kestra 唯一、L1/L2 角色、移除 cron/Windmill 图 |
| v1.0 | 2026-06-09 | 首版 |
