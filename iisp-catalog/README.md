# IISP Catalog

团队共建的配置目录仓（Git 源-of-truth）。各 IISP 实例通过 Catalog Provider 同步到本地 `catalog_cache/`。

> **编排（v2.2）**：Edge + Hub **统一 Kestra**。历史文档中 Windmill、cron、`iisp flow run` 生产路径已废弃；以 [`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) 为准。

## 目录

- `strategies/` — 数据收集策略 JSON
- `pipelines/kestra/` — **运行时权威**：Kestra Flow YAML（Edge + Hub）
- `pipelines/legacy/` — 设计态 Pipeline DSL（编译 → `kestra/`）
- `pipelines/demo/` — 演示 Flow
- `environments/` — 环境 → release 绑定
- `releases.yaml` — 发布清单
- `tool-pins.yaml` — 各环境工具版本锁定
- `skills-index.yaml` — 技能元数据索引

## 编排模型

**Edge + Hub 统一 Kestra**；Flow 存放在 `pipelines/kestra/`，Kestra Git sync 加载。

| 场景 | 用法 |
|------|------|
| **生产调度** | Kestra Cron / 事件 → `POST /v1/tools/{id}/invoke` |
| **本地 dev** | `./scripts/iisp flow run <flow_id>`（dry-run，非生产） |

设计态 Pipeline DSL（`pipelines/legacy/` 或 `demo/`）可编译为 Kestra YAML 后合入 `kestra/`。

## 贡献流程

1. Fork 本仓或在本仓创建分支
2. 修改策略/流水线后提交 PR
3. CODEOWNERS 审核合并
4. 各实例 sync（见下方环境变量）

## 环境变量（部署侧）

| 变量 | 说明 |
|------|------|
| `IISP_CATALOG_PROVIDER` | `git`（默认）或 `local` |
| `IISP_CATALOG_REPO` | Git 仓库 URL；留空则使用主仓内置 `iisp-catalog/` |
| `IISP_CATALOG_REF` | 分支或 tag，默认 `main` |
| `IISP_CATALOG_LOCAL` | `local` Provider 时的目录路径 |
| `IISP_CATALOG_SYNC_ON_START` | `1` 时启动自动 sync |

## 迁移

- **GitHub → 内网 Git**：改 `IISP_CATALOG_REPO` 即可
- **断网 / NAS**：`IISP_CATALOG_PROVIDER=local` + `IISP_CATALOG_LOCAL`
- **Nacos / bundle**：规划中，见 [CATALOG_CENTER.md](../docs/CATALOG_CENTER.md)

## 同步命令

```bash
./scripts/iisp catalog sync
curl -X POST http://127.0.0.1:5050/api/catalog/sync
curl http://127.0.0.1:5050/api/catalog/status
```
