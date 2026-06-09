---
name: iisp-review-pr
description: >-
  Reviews IISP pull requests for architecture violations, missing validate,
  Tool cross-imports, and workflow_engine changes. Use before commit, before
  PR, or when user asks to review IISP changes.
---

# IISP PR 审查清单

对照 [`docs/CODING_STANDARDS.md`](../../docs/CODING_STANDARDS.md) §9–§10。

## 1. 变更分类

- [ ] 新 Tool  
- [ ] 新 Pipeline  
- [ ] 平台 Core（需平台组）  
- [ ] 前端 UI  
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
python -m pytest <paths> -q
```

## 4. Tool PR 额外项

- [ ] `tool.manifest.json` 与 SKILL `name` 一致  
- [ ] `contract_version: v1`  
- [ ] `invoke.py` 仅映射，`service.py` 含业务  
- [ ] outputs 可 JSON 序列化  
- [ ] 有基本测试  

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

**零红线 + validate 全过 + diff 范围合理** 方可 approve。
