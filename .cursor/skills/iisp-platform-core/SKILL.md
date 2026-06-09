---
name: iisp-platform-core
description: >-
  Guides changes to IISP Platform Core only — Gateway, Registry, catalog sync,
  flow_runner, MCP server. Use when editing server/, core/, orchestration/,
  capabilities/registry, or app entry — not for new business Tools.
---

# IISP Platform Core 开发

**仅平台组** 或经 CODEOWNERS 审批后修改 Core。

## Core 范围

| 模块 | 路径 |
|------|------|
| Gateway | `server/routes/tools.py` → 演进 `core/gateway/` |
| Registry | `capabilities/registry.py` |
| Catalog | `orchestration/catalog_*` |
| flow_runner | `orchestration/flow_runner.py` |
| MCP | `mcp/iisp_server.py` |
| 入口 | `app.py`, `server/factory.py` |

## 必须遵守

1. Gateway **不含**业务组合（if query then qc）  
2. 新 API 进 OpenAPI / Pydantic 校验  
3. Tool 执行仅经 Registry + lazy import  
4. 不扩展 `workflow_engine`；向删除 scheduler 靠拢  
5. 改动同步 **文档**：`IISP_DESIGN_FINAL.md` 或附录  

## 禁止

- 在 Core 为单一业务场景硬编码  
- 破坏 Tool Contract v1  
- 引入运行时 LLM 调度  

## 测试

```bash
python -m pytest tests/ -q
```

## 业务需求来了怎么办？

→ 指导贡献者使用 `iisp-create-tool` + `iisp-compose-flow`，**不要**在 Core 实现业务。

参考：[`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md) §7
