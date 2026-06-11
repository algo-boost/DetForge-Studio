# IISP Tool 编码

完整规范：`docs/CODING_STANDARDS.md` §4。

## 结构

`tool.manifest.json` + `invoke.py` + `service.py`

## 必须

- `contract_version: v1`
- `handle` 返回 `status`: done|failed|skipped|waiting_human|accepted
- 仅依赖 `packages/platform`，不 import 其他 Tool

## 提交前

```bash
./scripts/iisp tool validate path/to/tool.manifest.json
python -m pytest tools/<id>/tests/ -q
```

Skill：**iisp-create-tool** · **iisp-tool-package**
