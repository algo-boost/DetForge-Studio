# IISP 项目级约束

实现与文档以 **`docs/IISP_DESIGN_FINAL.md`** 为唯一架构定稿。

## 三条铁律 + 工程纪律

1. **编排零自研 DAG** — **唯一编排器：Kestra**（Edge + Hub）
2. **契约唯一** — 集成只通过 `POST /v1/tools/{id}/invoke` 与 Catalog Pipeline YAML
3. **AI 只写文件** — 仅改允许路径；运行态无 LLM
4. **变更必记录** — 用户可见功能须同 PR 更新 `docs/PLATFORM_CHANGELOG.md`（Skill：**iisp-record-platform-change**）
5. **功能必带测** — 运行时代码变更须同 PR 交付单元测试（Skill：**iisp-unit-tests**）

## 禁止

- 扩展 `workflow_engine` / `workflow_scheduler` 作主编排
- Tool 之间 `import` 对方 `service.py`
- 在 Gateway 写业务组合 if-else
- 跳过 `iisp tool validate` / `iisp workflow validate`
- 提交 `config.json`、密钥

## 项目 Skills

权威目录：**`agent/skills/`**（Cursor 通过 `.cursor/skills/` 符号链接加载）

| Skill | 场景 |
|-------|------|
| `iisp-vibe-guardrails` | 任何 IISP 开发前 |
| `iisp-skill-author` | L2：写 Platform Skill |
| `iisp-compose-flow` | 新 Kestra Flow |
| `iisp-review-pr` | PR 前审查 |

完整索引：`agent/skills/README.md` · 机器可读：`./scripts/iisp agent context --json`
