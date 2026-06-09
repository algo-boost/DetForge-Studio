# IISP Catalog

团队共建的配置目录仓（Git 源-of-truth）。各 IISP 实例通过 Catalog Provider 同步到本地 `catalog_cache/`。

**关联**：[**最终定稿**](../docs/IISP_DESIGN_FINAL.md) · [平台说明](../docs/IISP_PLATFORM.md)

## 目录

- `strategies/` — 数据收集策略 JSON
- `pipelines/demo/` — 演示 Flow（如 `welcome_demo`）
- `pipelines/legacy/` — Pipeline DSL（Edge 可直接 `iisp flow run`）
- `pipelines/kestra/` — Hub：Kestra 原生 Flow YAML（可选）
- `environments/` — 环境 → release 绑定
- `releases.yaml` — 发布清单
- `tool-pins.yaml` — 各环境工具版本锁定
- `skills-index.yaml` — 技能元数据索引

## 编排模型

| 部署 | 用法 |
|------|------|
| **Edge** | `cron` + `./scripts/iisp flow run <flow_id>` |
| **Hub** | Kestra / Windmill 调 `POST /v1/tools/{id}/invoke` |

Pipeline YAML 为权威配置；Kestra YAML 可由编译器生成或单独维护。

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
