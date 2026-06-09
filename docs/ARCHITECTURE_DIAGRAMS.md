# IISP 技术架构图集

**版本**：v1.0  
**日期**：2026-06-09  
**关联**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) · [`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md) · [`CODING_STANDARDS.md`](./CODING_STANDARDS.md)

> 本文集中存放架构图，便于评审、 onboarding 与 Agent 引用。实现细节以设计定稿为准。

---

## 1. C4 上下文（系统与外部）

```mermaid
C4Context
  title IISP 系统上下文

  Person(qc, "质检员", "审图、上传 COCO")
  Person(algo, "算法工程师", "查询、Flow、模型")
  Person(ops, "运维", "部署、Catalog、Kestra")
  Person(vibe, "Vibe 贡献者", "Cursor 开发 Tool/Pipeline")

  System(iisp, "IISP Platform", "Tool Gateway + Shell + Catalog Client")
  System_Ext(kestra, "Kestra / Windmill", "Hub 编排")
  System_Ext(git, "Git iisp-catalog", "策略与 Pipeline")
  System_Ext(mf, "Magic-Fox", "训练平台")
  System_Ext(vb, "vision_backend", "产线库")
  System_Ext(n8n, "n8n", "通知")
  System_Ext(cursor, "Cursor + MCP", "设计态 Agent")

  Rel(qc, iisp, "浏览器")
  Rel(algo, iisp, "浏览器")
  Rel(ops, iisp, "管理")
  Rel(vibe, cursor, "Vibe Coding")
  Rel(cursor, git, "PR")
  Rel(iisp, git, "catalog sync")
  Rel(kestra, iisp, "HTTP invoke")
  Rel(iisp, vb, "查询")
  Rel(iisp, mf, "同步")
  Rel(n8n, kestra, "Webhook")
```

---

## 2. C4 容器（部署单元）

```mermaid
flowchart TB
  subgraph clients [客户端]
    Browser[浏览器 React Shell]
    CursorIDE[Cursor IDE]
  end

  subgraph edge [Edge 节点]
    IISP_E[IISP :5050]
    MySQL_E[(MySQL)]
    Redis_E[(Redis 可选)]
    Cron_E[cron]
  end

  subgraph hub [Hub 节点]
    IISP_H[IISP Gateway]
    Kestra[Kestra]
    PG[(Postgres)]
    Redis_H[(Redis)]
    MySQL_H[(MySQL)]
  end

  subgraph git [配置]
    Catalog[iisp-catalog Git]
  end

  subgraph embed [子应用 可选]
    Viz[COCOVisualizer :viz]
    Unify[DetUnify :unify]
  end

  Browser --> IISP_E
  Browser --> IISP_H
  Browser --> Viz
  Browser --> Unify
  CursorIDE -->|MCP dev| IISP_H
  Cron_E -->|flow run| IISP_E
  IISP_E --> MySQL_E
  IISP_E --> Redis_E
  Kestra -->|invoke| IISP_H
  IISP_H --> Redis_H
  IISP_H --> MySQL_H
  Kestra --> PG
  Catalog -->|sync| IISP_E
  Catalog -->|sync| IISP_H
  Kestra -->|git sync| Catalog
```

---

## 3. 逻辑分层

```mermaid
flowchart TB
  subgraph L5 [L5 设计态]
    Agent[Cursor Agent + Skills]
    MCP[MCP Server]
  end

  subgraph L4 [L4 配置 Catalog]
    Strat[strategies]
    Pipe[pipelines]
    Rel[releases]
  end

  subgraph L3 [L3 编排 Orchestration]
    K[Kestra Hub]
    C[cron + flow run Edge]
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

  Agent --> MCP
  Agent -->|PR| L4
  L4 --> L3
  C --> GW
  K --> GW
  GW --> OAS
  GW --> T1 & T2 & T3 & TN
  T1 --> VB
  T2 & T3 --> DF
  T3 --> FS
```

---

## 4. Tool 调用序列（Hub）

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
  Note over K,G: params 含 steps.query.outputs.task_id
```

---

## 5. 人工卡点序列

```mermaid
sequenceDiagram
  participant O as 编排 Kestra/flow run
  participant G as Gateway
  participant U as 用户 UI
  participant R as Resume API

  O->>G: invoke export
  G-->>O: done batch_id
  O->>G: invoke gate / next
  G-->>O: waiting_human + resume.token
  O->>O: Pause / 写 pause 文件
  U->>U: /curation 上传 COCO
  U->>R: POST /v1/orchestration/resume
  R->>O: resume
  O->>G: invoke import
  G-->>O: done
```

---

## 6. Vibe Coding 设计态

```mermaid
flowchart LR
  subgraph human [人]
    NL[自然语言]
  end

  subgraph cursor [Cursor]
    SK[Skills]
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
    YAML[pipelines/*.yaml]
  end

  subgraph gate [门禁]
    V[CLI validate]
    CI[GitHub CI]
  end

  AG --> mcp
  AG --> out
  out --> V --> CI
  CI -->|merge| RUN[运行态 无 LLM]
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
  Flow[flow_runner / Kestra]

  GH --> PR --> GH
  GH --> Sync --> Cache
  Cache --> Strat
  Cache --> Flow
```

---

## 8. 前端组件关系（目标）

```mermaid
flowchart TB
  Shell[App Shell Layout]
  Home[HomePage 工作台]
  Work[作业页 + SceneHubNav]
  Flows[FlowsCatalog + Runs]
  Plat[Toolbox + Config]

  Shell --> Home & Work & Flows & Plat
  Work --> API[api/client.js]
  Flows --> API
  Plat --> API
  API --> GW[Flask /v1]
  Home --> Todo[TodoList]
  Home --> Tray[GlobalTaskStrip]
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

  Orch[Kestra/cron/UI] -->|HTTP only| GW[Gateway]
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
  M2 Kestra 生产 Flow        :m2, after m1, 2026-08
  M3 tools 标准包 UI 工作台   :m3, after m2, 2026-09
  M4 删 workflow_engine      :m4, after m3, 2026-10
  section Agent A
  A1 Skills Rules 文档       :done, a1, 2026-06, 2026-06
  A2 agent context           :a2, 2026-06, 2026-07
  A3 validate 加强           :a3, after a2, 2026-07
  A4 MCP Server              :a4, after a3, 2026-07
  section UI U
  U1 工作台                  :u1, 2026-06, 2026-07
  U2 四域导航                :u2, after u1, 2026-07
  U3 流水线页                :u3, after u2, 2026-08
```

---

## 11. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | C4、容器、序列、Vibe、路线图 |
