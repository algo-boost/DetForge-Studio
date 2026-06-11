# IISP Pipeline / Kestra Flow

规范：`docs/IISP_DESIGN_FINAL.md` v2.2 · `docs/TOOLBOX_ORCHESTRATION.md`

## 必须

- **生产编排**：`iisp-catalog/pipelines/kestra/`
- 每步 `POST /v1/tools/{id}/invoke`；人工卡点用 **Pause**
- `tool_id` 必须存在于 Registry

## 禁止

cron 生产调度、Windmill、YAML 内嵌 Python/SQL、编造 tool_id

## 提交前

```bash
./scripts/iisp workflow validate path/to/flow.yaml
./scripts/iisp flow list-kestra
```

Skill：**iisp-compose-flow**
