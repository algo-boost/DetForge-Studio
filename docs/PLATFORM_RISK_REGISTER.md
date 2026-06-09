# IISP 平台风险与遗漏清单

**版本**：v1.1  
**标准**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) v2.2 · [`DOCS_INDEX.md`](./DOCS_INDEX.md)  
**日期**：2026-06-09  
**用途**：架构/产品评审 — 当前设计**尚未覆盖或仅浅层提及**的问题  
**关联**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) · [`SECURITY.md`](./SECURITY.md) · [`PRODUCT_DESIGN.md`](./PRODUCT_DESIGN.md)

> 本文不是「已知 bug 列表」，而是**系统性遗漏**与**建议纳入路线**的议题。已列入 M/S/U/A 路线的不再重复。

---

## 1. 安全与身份（除 Token 外）

| 议题 | 现状 | 建议 |
|------|------|------|
| 用户登录 / RBAC | 未做 | S5 + OIDC（见 SECURITY） |
| Tool invoke 授权 | 有 Token 则全权限 | scope：qc 不可调 admin config |
| 路径遍历 | exports/uploads 需审查 | 规范化路径、禁止 `..` |
| 子进程注入 | predict/CLI 调外部脚本 | 白名单命令、无 shell=True |
| `.iisp-tool` 供应链 | 未做 | 包签名 + hash pin |
| CSRF | SPA + Cookie 登录后需考虑 | S5 时 SameSite + CSRF token |
| 依赖漏洞 | 无固定 CI | pip/npm audit 进 CI |

---

## 2. 可靠性与运维

| 议题 | 现状 | 建议 |
|------|------|------|
| **备份恢复** | 文档未写 RPO/RTO | config + detforge + catalog 备份手册 |
| **灾难恢复** | 无 | Edge 一键恢复包；Hub DB 复制 |
| **健康检查** | 部分 | `/health` + DB/Redis/Kestra 依赖探针 |
| **优雅停机** | worker 子进程 | drain 队列后再停 |
| **配置漂移** | 多 Edge 手工 config | 可选 Nacos 或 config 模板仓 |
| **版本兼容** | Tool Manifest version | `tool-pins.yaml` 强制 CI |
| **Runbook** | 无 | Flow 失败、卡 human、DB 满 |

---

## 3. 编排与数据一致性

| 议题 | 现状 | 建议 |
|------|------|------|
| **幂等性** | 文档提 Idempotency-Key | Gateway 去重表 + Kestra 重试安全 |
| **并发 Flow** | Edge 未限 | 同 flow_id 互斥（文件锁或 DB） |
| **Catalog sync 竞态** | sync 覆盖 cache | 运行中 Flow 读旧/新 YAML 策略：sync 后版本号 pin |
| **部分失败补偿** | 无 Saga | 文档化 manual 步骤；关键 Flow 人工 checklist |
| **时钟 skew** | 有时区工具 | **Kestra** Cron 统一 UTC + UI 显示本地 |
| **Dead letter** | RQ 失败任务 | 失败队列 + UI 可见 |

---

## 4. 性能与资源

| 议题 | 现状 | 建议 |
|------|------|------|
| **invoke 内存** | 文档要求 lazy import | Gateway `max_concurrent` 信号量 |
| **invoke 超时** | 未统一 | 每 Tool Manifest `timeout_sec` |
| **大文件** | 256MB 上传上限 | 流式上传、对象存储 |
| **query 爆内存** | 策略 MAX_ROWS | invoke 校验 + 硬顶 |
| **连接池** | MySQL | pool size 与 worker 数文档化 |

---

## 5. 可观测性

| 议题 | 现状 | 建议 |
|------|------|------|
| **指标** | OTel 规划 | invoke 延迟、队列深度、Flow 成功率 |
| **告警** | 无 | n8n：Flow failed、disk、DB 连接 |
| **链路追踪** | 无 | `run_id` 贯穿 log |
| **业务看板** | Metabase 规划 | 与产品 KPI 对齐 |

---

## 6. 产品与体验

| 议题 | 现状 | 建议 |
|------|------|------|
| **多项目/租户** | 单 forge DB | Hub：`project_id` 命名空间 |
| **国际化** | 中文为主 | 内部工具可暂缓 |
| **无障碍** | QC 快捷键部分 | 质检页 a11y 审计 |
| **离线/air-gap** | bundle Provider 规划 | 导出/导入 runbook |
| **移动端** | 未考虑 | 质检仅桌面即可 |

---

## 7. 数据治理

| 议题 | 现状 | 建议 |
|------|------|------|
| **数据保留** | exports 膨胀 | TTL 清理 job + 策略 |
| **PII/产线数据** | 查询落盘 CSV | 目录权限、脱敏导出选项 |
| **审计「谁看了哪张图」** | 无 | Hub 合规场景加 audit |
| **跨环境数据** | dev 连 prod DB 风险 | config 环境标签 + 启动警告 |

---

## 8. 共建与 Agent

| 议题 | 现状 | 建议 |
|------|------|------|
| **恶意 Tool PR** | validate 语法 | 沙箱试运行、CODEOWNERS |
| **Pipeline 删 prod 数据** | 无 guard | 危险 tool 标签 + 二次确认 |
| **Agent 幻觉 tool** | A3 validate | CI 必过 |
| **Skill 版本** | 项目 skills | CHANGELOG |

---

## 9. 测试与质量

| 议题 | 现状 | 建议 |
|------|------|------|
| **Flow 集成测试** | demo 单测 | CI 用 mock invoke 跑 validate + 干跑 |
| **契约测试** | 无 | OpenAPI contract test |
| **E2E** | 手工 | Playwright 冒烟：查询 + demo flow |
| **负载测试** | 无 | invoke 并发基线 |

---

## 10. 法律与合规

| 议题 | 现状 | 建议 |
|------|------|------|
| **开源许可证** | submodule 多 | SBOM / 许可证清单 |
| **产线数据出境** | 未写 | 部署约束进客户交付文档 |

---

## 11. 优先级矩阵（建议）

```text
        影响高
          │
  P0 安全 │  api_token 生产必开、Catalog secret scan、路径遍历
          │  S1–S2 Token 轮换与 401 引导
  ────────┼────────────────────────────
  P1 可靠 │  备份、health、幂等、DLQ
          │
  P2 治理 │  审计、保留、scoped token、多项目
          │
  P3 体验 │  OIDC、工作台、E2E
        影响低 ──────────────────→ 紧迫度高
```

---

## 12. 与路线图挂钩

| 遗漏项 | 建议并入 |
|--------|----------|
| Token 管理 S1–S5 | [`SECURITY.md`](./SECURITY.md) |
| Gateway scope/audit | **M1** |
| Resume token TTL | **M2** |
| OIDC | **M5** / **S5** |
| 工作台/待办 | **U1** |
| gitleaks CI | **S1** 或 CI 模板 |
| 备份 runbook | 运维文档 **O1**（新建） |

---

## 13. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 首版风险登记 |
