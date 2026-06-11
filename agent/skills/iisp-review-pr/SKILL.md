---
name: iisp-review-pr
description: >-
  Reviews IISP pull requests for architecture violations, missing validate,
  missing PLATFORM_CHANGELOG, Tool cross-imports, and workflow_engine changes.
---

# IISP PR 审查清单

对照 [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md) §9–§10。

## 1. 变更分类

- [ ] 新 Tool  
- [ ] 新 Pipeline / Kestra Flow  
- [ ] 平台 Core（需平台组）  
- [ ] 前端 UI（含 L1/L2 导航）  
- [ ] **平台功能变更记录**（`PLATFORM_CHANGELOG.md`）  
- [ ] 文档 only  

## 2. 架构红线（任一命中则要求修改）

- [ ] 修改了 `workflow_engine` / `workflow_scheduler` 且非删除/迁移  
- [ ] Tool A import Tool B 的 `service.py`  
- [ ] Gateway 新增「组合多个 tool」的业务逻辑  
- [ ] Pipeline 引用未注册 `tool_id`  
- [ ] 在 DB 新增 workflow 模板作为权威  
- [ ] 提交 `config.json`、`.config.key`、密钥  

## 3. 校验命令（必须贴出结果或 CI 绿）

```bash
./scripts/iisp tool validate <manifest>
./scripts/iisp workflow validate <yaml>
python -m pytest <paths> -q    # 与功能同 PR，见 iisp-unit-tests
```

## 3.0 单元测试（强制）

- [ ] **运行时代码变更**已包含同 PR 单元测试（Skill：**iisp-unit-tests**）
- [ ] pytest 覆盖本次新增/修改模块（非全仓无关跳过）
- [ ] Bugfix PR 含复现测试（或说明无法稳定复现的原因）

**有功能逻辑但无测试 → 结论：需修改**（文档-only PR 除外）

## 3.1 变更记录（用户可见功能必填）

- [ ] 已更新 [`docs/PLATFORM_CHANGELOG.md`](../../docs/PLATFORM_CHANGELOG.md) `[Unreleased]`（Skill：**iisp-record-platform-change**）
- [ ] 已同步关联文档（`PRODUCT_DESIGN` / `releases.yaml` / `USER_GUIDE` 等，见 PLATFORM_CHANGELOG §映射表）
- [ ] 或 PR 明确标注「无用户可见变更」

**任一用户可见功能变更但无 changelog → 结论：需修改**

## 4. Tool PR 额外项

- [ ] `tool.manifest.json` 与 SKILL `name` 一致  
- [ ] `contract_version: v1`  
- [ ] `invoke.py` 仅映射，`service.py` 含业务  
- [ ] outputs 可 JSON 序列化  
- [ ] **同 PR 单元测试**（`pytest`，见 **iisp-unit-tests**）  

## 5. Pipeline PR 额外项

- [ ] 每个 `nodes[].tool` ∈ Registry  
- [ ] 模板语法 `{{params}}` / `{{steps}}` 正确  
- [ ] 人工步骤 `notes` 含 UI 路径  
- [ ] `releases.yaml` 更新（若上线）  

## 6. 输出格式

```markdown
## 审查结果
- 结论：通过 / 需修改
- 红线：无 / 列表
- 缺失校验：…
- 建议：…
```

## 7. 通过标准

**零红线 + validate 全过 + 同 PR 单元测试（或注明无运行时代码）+ changelog 合规 + diff 范围合理** 方可 approve。
