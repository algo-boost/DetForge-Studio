---
name: iisp-skill-pack
description: >-
  Packs an IISP Platform Skill (SKILL.md) into a loadable platform tool with
  manifest, CLI, invoke, and default UI. Use after skill-author, when user says
  pack skill, install tool, register skill, or convert SKILL to platform tool.
---

# IISP Skill 封装（Skill → 平台工具）

**规范**：[`docs/SKILL_PLATFORM.md`](../../docs/SKILL_PLATFORM.md) · [`docs/TOOL_PLUGIN_MODEL.md`](../../docs/TOOL_PLUGIN_MODEL.md)

## 何时使用

用户已有 **`skills/<id>/SKILL.md`**（或 Tool 目录内 SKILL），要变成**工具箱可加载、CLI 可调用、编排可引用**的工具。

## 封装流程

### 1. 校验 Skill

```bash
./scripts/iisp skill validate skills/<id>/SKILL.md
./scripts/iisp skill pack skills/<id>/SKILL.md --out tools/<id>/
./scripts/iisp skill pack skills/<id>/SKILL.md --install
```

`init-from-skill` 仍可用；**pack** = validate + init + `contract_version: v1` + `entry.invoke`。

人工检查：

- [ ] `name` 合法、与目录一致  
- [ ] `## 输入` / `## 输出` 完整  
- [ ] `## 实现` kind 正确  
- [ ] `ui_level: schema` 除非确需 wizard/custom  

### 2. 按 kind 补全

| kind | Agent 动作 |
|------|------------|
| **script** | 确保 `scripts/*.py` 存在；stdout 符合 Contract；必要时用 skill-sdk |
| **capability** | 实现 `service.py` / `capability.py` 的 TODO |
| **http** | Manifest `runtime: http` + `base_url` |

### 3. 生成/更新 Tool 包

必须存在：

```text
tools/<id>/
├── tool.manifest.json   # contract_version: v1
├── invoke.py
├── cli.py
├── SKILL.md             # 副本
├── tests/
└── ui.manifest.json     # 从 ## UI 生成（wizard/schema）
```

**Manifest 必须**：

- `skill_source` 指向源 Skill 路径  
- `outputs` 与 Skill `## 输出` 一致  
- `kind` 逐步从 `hybrid` 迁到标准 `runtime` 字段  

### 4. 校验 Tool

```bash
./scripts/iisp tool validate tools/<id>/tool.manifest.json
python -m pytest tools/<id>/tests/ -q
```

### 5. 索引

- 更新 `iisp-catalog/skills-index.yaml`（label、contributors）  
- 若上新 Flow：**iisp-compose-flow**  

## UI 服从平台

| Skill `## UI` | 平台行为 |
|---------------|----------|
| `mode: schema` 或省略 | **不要**写 React；工具箱 RJSF |
| `mode: wizard` | 生成 `ui.manifest.json` 步骤 |
| `mode: custom` | 仅此时创建 `ui/`；需专业规范 |

L2 用户：**默认 schema**，封装时避免不必要的 custom UI。

## 协议自检

- [ ] invoke/cli stdout 单行 JSON，`status` 合法  
- [ ] 无 import 其他 Tool  
- [ ] 无 Platform Core 改动  
- [ ] 无 Skill 内明文密钥  

## 输出给用户

```markdown
## 封装结果
- tool_id: …
- CLI: echo '{"params":{}}' | python -m tools.<id>.cli
- 工具箱: 重启或 catalog sync 后可见
- 编排: 在 Flow 中使用 tool: <id>
```

## 规划命令（文档先行）

已实现 CLI（见上）。`--install` 会 reload Registry。
