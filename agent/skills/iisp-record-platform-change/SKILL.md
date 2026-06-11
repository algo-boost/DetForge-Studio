---
name: iisp-record-platform-change
description: >-
  Records and synchronizes IISP platform functional changes in PLATFORM_CHANGELOG.md
  and related docs. Use when adding/changing/removing user-visible features, APIs,
  Tools, Kestra Flows, L1/L2 UI, security, or architecture standards — mandatory
  in the same PR as the code change.
---

# IISP — 平台功能变更同步记录

**强制**：平台功能发生修改时，**同一 PR** 内必须更新变更记录与关联文档。  
**权威 changelog**：[`docs/PLATFORM_CHANGELOG.md`](../../docs/PLATFORM_CHANGELOG.md)

## 何时必须触发本 Skill

| 命中任一项 | 必须记录 |
|------------|----------|
| 新/改/删 **Tool**、Manifest、invoke 契约 | ✅ |
| 新/改/删 **Kestra Flow**、Pipeline、定时策略 | ✅ |
| **API** 路径、请求/响应、status 枚举 | ✅ |
| **前端** 导航、页面、L1/L2 可见行为 | ✅ |
| **角色/权限**、工作台、待办逻辑 | ✅ |
| **部署**（compose、端口、环境变量） | ✅ |
| **安全/Token** 行为变更 | ✅ |
| **架构标准**变更（如编排选型） | ✅ `Docs` + `IISP_DESIGN_FINAL` 修订 |
| 纯 refactor、测试、注释，**行为不变** | ❌ 不必记；PR 写「无用户可见变更」 |

## 工作流（与代码改动同 PR）

### 1. 写 changelog 条目

编辑 [`docs/PLATFORM_CHANGELOG.md`](../../docs/PLATFORM_CHANGELOG.md) 的 **`## [Unreleased]`**：

```markdown
### Added
- **[数据查询]** L1 新增「日常捞数」场景卡片（交付工程师）
  - 技术：query + strategy `daily_trawl`
  - 文档：PRODUCT_DESIGN §4.1
```

分类：`Added` | `Changed` | `Deprecated` | `Removed` | `Fixed` | `Security` | `Docs`

**每条必须**：
- 用户可感知的一句话（中文）
- 注明 **L1 / L2 / 运维** 谁受影响
- 可选：`tool_id`、Flow id、API 路径

### 2. 按类型同步文档（不可只改 changelog）

| 变更 | 同步文件 |
|------|----------|
| 新 Tool | `iisp-catalog/skills-index.yaml`（若索引）；`PRODUCT_DESIGN` §6 阶段列 |
| 新 Flow 上线 | `iisp-catalog/releases.yaml` |
| 产品/角色/IA | `docs/PRODUCT_DESIGN.md` |
| L1 操作说明 | `docs/USER_GUIDE.md` 或 `USER_GUIDE_OPERATOR.md`（规划） |
| API/部署 | `docs/IISP_PLATFORM.md` |
| 编排细节 | `docs/TOOLBOX_ORCHESTRATION.md`（少改，重大才动） |
| 架构决策 | `docs/IISP_DESIGN_FINAL.md` 修订记录 + 必要时正文 |
| 新标准/索引 | `docs/DOCS_INDEX.md` |

**不要**改归档文档（`ARCHITECTURE_FINAL`、`GREENFIELD` 等）。

### 3. Catalog 子仓变更

若只改 `iisp-catalog/` 且影响 Flow/策略发布：
- 本文 `[Unreleased]` **或** [`iisp-catalog/CHANGELOG.md`](../../iisp-catalog/CHANGELOG.md)（二选一至少一处；**跨 Tool+Flow 的大功能两者都写摘要**）

### 4. PR 自检

在 PR 描述增加：

```markdown
## 变更记录
- [ ] 已更新 `docs/PLATFORM_CHANGELOG.md` [Unreleased]
- [ ] 已同步：PRODUCT_DESIGN / USER_GUIDE / releases.yaml / …（列出实际改动的）
- [ ] 无用户可见变更（如适用，说明原因）
```

### 5. 发版时（人工/运维）

将 `[Unreleased]` 整块移至新日期标题 `## [YYYY-MM-DD]`，并清空 `[Unreleased]` 各节。

## 与其他 Skill 的关系

| 顺序 | Skill |
|------|-------|
| 开发前 | **iisp-vibe-guardrails** |
| 开发中 | iisp-skill-author / compose-flow / create-tool / platform-core |
| **功能完成后、PR 前** | **本 Skill** + **iisp-review-pr** |

**禁止**：功能已改但 PR 未含 `PLATFORM_CHANGELOG.md` 更新 — `iisp-review-pr` 应判 **需修改**。

## Agent 输出模板

完成代码后，向用户汇报：

```markdown
## 变更同步
- Changelog：`PLATFORM_CHANGELOG.md` → [Unreleased] / Added: …
- 同步文档：…
- 未改文档原因：…（仅 internal 时）
```

## 禁止

- 只在口头/聊天说明变更，不写文件
- 只改 README 不改 `PLATFORM_CHANGELOG.md`
- 把架构标准变更藏在 commit message 里不更新 DOCS_INDEX / DESIGN_FINAL
