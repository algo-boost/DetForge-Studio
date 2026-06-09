# IISP Catalog 配置中心

**标准**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) v2.2 · [`DOCS_INDEX.md`](./DOCS_INDEX.md) · [`TOOLBOX_ORCHESTRATION.md`](./TOOLBOX_ORCHESTRATION.md)

---

## 1. 角色

`iisp-catalog` 是 IISP 的 **配置源-of-truth**（不是应用代码仓）：

| 内容 | 目录 | 消费者 |
|------|------|--------|
| 数据收集策略 | `strategies/` | 查询页、query tool |
| 流水线定义 | `pipelines/kestra/` | **Kestra** Git sync |
| 发布清单 | `releases.yaml` | UI 展示「已上线 Flow」 |
| 环境绑定 | `environments/*.yaml` | 各实例 pin 到某 release |
| 工具版本 | `tool-pins.yaml` | Gateway 校验 |

各部署实例通过 **Catalog Sync** 拉取到本地 `catalog_cache/`，不直接改生产缓存。

---

## 2. Provider 架构

```text
orchestration/catalog_providers/
├── base.py          # CatalogProvider 协议
├── git.py           # 默认：GitHub / 内网 Git
├── local.py         # NAS / 运维目录
└── __init__.py      # get_catalog_provider()
```

环境变量 **`IISP_CATALOG_PROVIDER`**：

| 值 | 说明 |
|----|------|
| `git` | 默认。`git clone` / `pull` 到 `catalog_cache/repo` |
| `local` | 只读挂载 `IISP_CATALOG_LOCAL` 目录 |
| `nacos` | 未实现；见 §5 |
| `bundle` | 未实现；离线包导入 |

### 2.1 Git Provider（推荐起步）

```bash
export IISP_CATALOG_PROVIDER=git
export IISP_CATALOG_REPO=https://github.com/your-org/iisp-catalog.git
export IISP_CATALOG_REF=main

./scripts/iisp catalog sync
```

- 支持 GitHub、GitLab、Gitea、内网 HTTP/SSH  
- **`IISP_CATALOG_REPO` 留空**：回退到主仓内置 `iisp-catalog/`（适合 demo）  
- 私有仓：部署机配置 deploy key 或 credential helper

### 2.2 Local Provider

```bash
export IISP_CATALOG_PROVIDER=local
export IISP_CATALOG_LOCAL=/mnt/nas/iisp-catalog

./scripts/iisp catalog sync
```

适用：无法出网、运维 rsync 到 NAS、临时验收包。

---

## 3. 同步行为

1. Provider `fetch()` 得到源目录  
2. 复制 `strategies/` → `catalog_cache/strategies/`  
3. 复制 `pipelines/` → `catalog_cache/pipelines/`  
4. 追加 `catalog_cache/sync_log.jsonl`（及 DB `catalog_sync_log` 若可用）

API：

```bash
curl http://127.0.0.1:5050/api/catalog/status
curl -X POST http://127.0.0.1:5050/api/catalog/sync
```

启动自动同步：`IISP_CATALOG_SYNC_ON_START=1`

---

## 4. 目录约定

```text
iisp-catalog/
├── README.md
├── CODEOWNERS
├── releases.yaml
├── tool-pins.yaml
├── skills-index.yaml
├── strategies/
│   └── *.json
├── pipelines/
│   ├── demo/                 # 演示（welcome_demo）
│   ├── legacy/               # Pipeline DSL，Edge 可直接 run
│   └── kestra/               # Hub：Kestra 原生 YAML（可选）
└── environments/
    └── dev-local.yaml
```

### releases.yaml

标记哪些 Flow 属于某次「发布」：

```yaml
releases:
  "2026.06.1":
    published_at: "2026-06-09T00:00:00Z"
    status: published
    pipelines:
      - id: welcome_demo
        path: pipelines/demo/welcome_flow.yaml
```

### environments/*.yaml

实例级绑定：

```yaml
env_id: prod-line-a
release: "2026.06.1"
pipelines:
  - daily_ng_curation
```

---

## 5. 迁移路径

### GitHub → 内网 Git

1. 镜像仓库到 Gitea/GitLab  
2. 修改 `IISP_CATALOG_REPO`  
3. `iisp catalog sync` 验证 commit

### Git → Local（断网）

1. `git archive` 或 rsync 到 NAS  
2. `IISP_CATALOG_PROVIDER=local`  
3. `IISP_CATALOG_LOCAL=/path/to/tree`

### 未来：Nacos

适用：**运行时**切换策略参数、feature flag，而非替代 Flow PR 流程。

规划接口：

- `IISP_CATALOG_PROVIDER=nacos`  
- `IISP_NACOS_SERVER`、`IISP_NACOS_NAMESPACE`、`IISP_NACOS_DATA_ID`  
- 内容与 Git 仓同 schema；sync 写入同一 `catalog_cache/` 布局

**建议**：Flow / 策略版本仍走 Git；Nacos 只做「实例生效哪一 release」或热更新小参数。

### 未来：Bundle

```bash
# 规划 CLI
iisp catalog export --out catalog-2026.06.1.tar.gz
iisp catalog import catalog-2026.06.1.tar.gz
```

用于 air-gap 交付；Provider `bundle` 读解压目录。

---

## 6. 贡献流程

1. Fork 或分支  
2. 修改 `strategies/` 或 `pipelines/`  
3. PR + CODEOWNERS  
4. 合并后各实例 `catalog sync`（或 webhook 触发）  
5. Hub 可选：Kestra Git 同步触发 Flow 更新

---

## 7. 与主仓关系

| 仓 | 内容 |
|----|------|
| **DetForge-Studio**（主仓） | 平台代码、内置 demo `iisp-catalog/`、capabilities |
| **iisp-catalog**（独立 Git，推荐） | 生产策略与 Flow、releases、环境配置 |

主仓内 `iisp-catalog/` 仅保留 **demo + 文档示例**；生产配置放在私有 Catalog 仓。

---

## 8. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | Provider 模型、GitHub 优先、迁移说明 |
