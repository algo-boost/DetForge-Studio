# IISP Agent 包（IDE 无关）

**任意 coding agent**（Cursor、Claude Code、Codex、OpenClaw、Windsurf 等）在本仓库协作时的**权威配置根目录**。

```
agent/
├── README.md           # 本文件 — 各 IDE 接入说明
├── manifest.yaml       # 人类可读索引
├── mcp.json.example    # MCP 配置范例（stdio）
├── skills/             # 项目 Skills（SKILL.md）
└── rules/              # 可移植规则（Markdown）
```

**入口文档**：仓库根 [`AGENTS.md`](../AGENTS.md)

**机器自举**：

```bash
./scripts/iisp agent context --json
```

输出 Skills 列表、Rules 路径、CLI 校验命令、MCP 规划 — **不依赖特定 IDE**。

---

## 设计原则

| 原则 | 说明 |
|------|------|
| **IDE 无关** | 业务约束在 `agent/`；各 IDE 仅做路径适配 |
| **单一事实源** | Skills 只在 `agent/skills/`；Cursor 用符号链接 |
| **CLI 兜底** | 无 Skill 加载能力时，`iisp agent context` + validate 命令仍可工作 |
| **MCP 标准接口** | list/validate 通过 MCP 暴露，任何支持 MCP 的 Agent 可接 |

---

## 各 Agent 接入

### Cursor

- Skills：`.cursor/skills/` → 符号链接至 `agent/skills/`
- Rules：`.cursor/rules/*.mdc`（globs；内容对齐 `agent/rules/`）
- MCP：复制 [`agent/mcp.json.example`](./mcp.json.example) → `.cursor/mcp.json`

### Claude Code

1. 读 [`AGENTS.md`](../AGENTS.md)（或根目录 [`CLAUDE.md`](../CLAUDE.md) 指针）
2. 将 `agent/rules/iisp-core.md` 作为项目约束注入上下文
3. 按需读取 `agent/skills/<name>/SKILL.md`
4. 运行 `./scripts/iisp agent context --json` 获取完整索引

### Codex / OpenAI Agents

1. 系统提示引用 `AGENTS.md`
2. 配置 MCP：[`agent/mcp.json.example`](./mcp.json.example)
3. 工具调用走 `iisp tool validate` 等 CLI（与 MCP 等价）

### OpenClaw / 其他

1. **`AGENTS.md`** 为通用贡献者指南（业界惯例，多 Agent 默认识别）
2. **`iisp agent context --json`** 供启动脚本拉取 Skills/Rules 列表
3. **`agent/manifest.yaml`** 供人类浏览；动态内容以 CLI JSON 为准

---

## Skills 与 Rules

| 类型 | 目录 | 说明 |
|------|------|------|
| Skills | [`skills/`](./skills/README.md) | 任务级操作手册（SKILL.md + YAML frontmatter） |
| Rules | [`rules/`](./rules/README.md) | 路径/全局约束（Markdown） |

---

## MCP（设计态，规划 A4）

实现后提供 `iisp_list_tools`、`iisp_validate_pipeline` 等 — **不提供生产 invoke**。

配置范例：[`mcp.json.example`](./mcp.json.example) · 规范：[`docs/IISP_DESIGN_FINAL.md`](../docs/IISP_DESIGN_FINAL.md) Part IX

---

## 设计态 vs 运行态

| | LLM / Agent | 说明 |
|---|-------------|------|
| **设计态** | ✅ | Agent 生成 Tool/Flow/Skill → validate → PR |
| **运行态** | ❌ | Kestra + Gateway invoke，无 LLM |

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-06-09 | 从 Cursor 专用目录拆出 `agent/` 权威包 |
