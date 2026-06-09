# IISP 平台功能变更记录

**版本**：v1.0  
**维护**：**任何平台功能变更必须与代码同一 PR 更新本文 `[Unreleased]`**  
**约束 Skill**： [`.cursor/skills/iisp-record-platform-change/SKILL.md`](../.cursor/skills/iisp-record-platform-change/SKILL.md)

> 本文记录 **对用户、L1/L2 角色、API、Tool、Flow、部署可见** 的变更。  
> 纯内部重构且行为不变 → 可不记，但须在 PR 说明「无用户可见变更」。  
> 架构定稿变更另记 `IISP_DESIGN_FINAL.md` 修订记录；Catalog 专项可记 `iisp-catalog/CHANGELOG.md`。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [Unreleased]

### Added

- （暂无）

### Changed

- （暂无）

### Deprecated

- （暂无）

### Removed

- （暂无）

### Fixed

- （暂无）

### Security

- （暂无）

### Docs

- 建立 `PLATFORM_CHANGELOG.md` 与 **iisp-record-platform-change** Skill
- 安装 [Karpathy guidelines](https://github.com/forrestchang/andrej-karpathy-skills)：`karpathy-guidelines.mdc` + Skill（通用编码约束）

---

## [2026-06-09] — 文档与标准 v2.2

### Docs

- **架构定稿 v2.2**：编排统一 **Kestra**（Edge + Hub）；废弃 Windmill、cron 生产路径
- **用户分层**：L1（交付/客户质检，只用）/ L2（SA/算法/光学，配置）
- **Skill-first**：L2 通过 Platform Skill 扩展 Tool（`SKILL_PLATFORM.md`）
- 新增 [`DOCS_INDEX.md`](./DOCS_INDEX.md) 作为文档入口
- 产品能力地图对齐飞书《数据闭环建设方案评审》子模块 + 组合模块

---

## 条目写法（复制模板）

```markdown
### Added | Changed | …
- **[模块/Tool/页面]** 一句话用户可感知说明（L1/L2 谁受影响）
  - 技术：`tool_id` / API 路径 / Flow id（可选）
  - 文档：已同步 `PRODUCT_DESIGN` §x / `USER_GUIDE`（如适用）
```

---

## 变更类型 → 必同步文档

| 变更类型 | 必更新 | 建议更新 |
|----------|--------|----------|
| 新 Tool | 本文 + `releases.yaml`（若上线） | `PRODUCT_DESIGN` §6、`skills-index.yaml` |
| 新 Kestra Flow | 本文 + `releases.yaml` | `PRODUCT_DESIGN` §3.3 |
| API `/v1` 变更 | 本文 + OpenAPI | `IISP_PLATFORM.md` |
| L1/L2 导航/权限 | 本文 | `PRODUCT_DESIGN` §4、`UI_REDESIGN_CHECKLIST` |
| 架构决策 | 本文（摘要） | `IISP_DESIGN_FINAL` 修订记录 |
| 安全/Token | 本文 `Security` | `SECURITY.md` |
| 仅文档 | 本文 `Docs` | `DOCS_INDEX`（若增删文档） |

---

## 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | 首版；与 iisp-record-platform-change Skill 配套 |
