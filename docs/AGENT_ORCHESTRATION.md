# Agent 编排协议（CLI-first）

**目标**：每个工具都是 CLI；编排 = 串 CLI；任意 Agent 可 **生成 YAML**、**校验**、**后台执行**，无需绑死 Cursor。

**契约**：[`TOOL_PLUGIN_MODEL.md`](./TOOL_PLUGIN_MODEL.md) §4.1 — `stdin/stdout` JSON 与 `POST /v1/tools/{id}/invoke` **同构**。

---

## 1. 一句话模型

```text
工具 = 一条 CLI 命令（stdin JSON → stdout JSON）
编排 = 按顺序调 CLI，上一步 outputs 填下一步 params
YAML = 把「串 CLI + 接线」写下来，交给 Kestra 定时/重试/历史
Agent = 读工具清单 → 写 YAML 或写 shell 链 → validate → 执行
```

Kestra Flow 里每一步 `http.Request`，等价于：

```bash
./scripts/iisp tool invoke <tool_id> --param k=v ...
```

---

## 2. Agent 启动（任意 IDE，第一步）

```bash
cd tools/DetForge-Studio
./scripts/iisp agent context --json    # Skills、Rules、CLI 索引
./scripts/iisp tool list               # 可用 tool_id（禁止编造）
```

读 Skill：**`agent/skills/iisp-compose-flow/SKILL.md`**（写 YAML）  
读规范：**`docs/FLOW_YAML_COMMENTS.md`**（中文注释必写）

---

## 3. 路径 A — Agent 生成 YAML（推荐生产）

| 步 | Agent 做什么 | 命令 |
|----|--------------|------|
| 1 | 澄清流程：步骤、策略、是否 Pause | 对话 |
| 2 | `iisp tool list` 确认 tool_id | CLI |
| 3 | 复制 `closed_loop_demo_smoke.yaml`，改步骤与 `←` `→` 注释 | 写文件 |
| 4 | 校验 | `./scripts/iisp workflow validate iisp-catalog/pipelines/kestra/<id>.yaml` |
| 5 | 提交 Catalog PR | git |
| 6 | 运行（人/CI/Kestra） | Shell `/flows` 或 Kestra Cron |

**Agent 产出物**：`iisp-catalog/pipelines/kestra/<flow_id>.yaml`（带中文注释）

**禁止**：Agent 在生产环境直接 `invoke` 写库（见 `AGENTS.md` 设计态 vs 运行态）；dev 可用路径 B。

---

## 4. 路径 B — Agent 直接串 CLI（dev / 一次性 / 无 Kestra）

不生成 YAML，用 shell 链（与 YAML 语义相同）：

```bash
# ① 查询
QUERY=$(./scripts/iisp tool invoke smoke-query --param row_count=2 --param strategy_id=smoke)
TASK_ID=$(echo "$QUERY" | python3 -c "import sys,json; print(json.load(sys.stdin)['outputs']['task_id'])")

# ② 建批次（把上一步 task_id 塞进 params）
BATCH=$(echo "{\"params\":{\"task_id\":\"$TASK_ID\",\"intent_type\":\"demo\"}}" \
  | ./scripts/iisp tool invoke curation-create)
BATCH_ID=$(echo "$BATCH" | python3 -c "import sys,json; print(json.load(sys.stdin)['outputs']['batch_id'])")

# ③ 导出 …
echo "{\"params\":{\"batch_id\":\"$BATCH_ID\"}}" | ./scripts/iisp tool invoke curation-export
```

**后台执行**：

```bash
nohup bash my_pipeline.sh > /tmp/run.log 2>&1 &
```

或交给 **Kestra**（路径 A 的 YAML）获得重试、历史、Cron。

---

## 5. 路径 C — Agent 生成 YAML 并触发 Kestra（运行态）

| 步 | 命令 / API |
|----|------------|
| 生成 + validate | 同路径 A |
| 触发执行 | `POST /api/flows/kestra/execute` 或 Shell `/flows` 点运行 |
| 查状态 | `GET /api/flows/runs/kestra:{execution_id}` |
| Resume | `POST /api/flows/runs/kestra:{id}/resume` |

**CLI**：`./scripts/iisp flow execute <flow_id> --param strategy_id=daily_trawl`

---

## 6. 给 Agent 的最小工具面（开放 CLI）

| 能力 | 已有 | 说明 |
|------|------|------|
| 自举索引 | ✅ `iisp agent context` | Skills + CLI 列表 |
| 列工具 | ✅ `iisp tool list` | |
| 调单工具 | ✅ `iisp tool invoke` / `tool run` | Contract v1 |
| 校验 Tool | ✅ `iisp tool validate` | |
| 校验 Flow | ✅ `iisp workflow validate` | |
| 列 Kestra Flow | ✅ `iisp flow list-kestra` | |
| 写 Flow Skill | ✅ `iisp-compose-flow` | |
| MCP 封装 | ✅ `mcp/iisp_server.py` | 见 `mcp/README.md` |
| CLI 触发 Kestra | ✅ `iisp flow execute` | 等价 `POST /api/flows/kestra/execute` |
| CLI 查状态 / Resume | ✅ `iisp flow status` / `resume` | run_key 如 `kestra:ex-xxx` |
| CLI 链模板生成 | ✅ `iisp flow export-shell` | dev 用 `tool invoke` 串链 |

---

## 7. Agent 系统提示模板（可复制）

```text
你是 IISP 编排 Agent。规则：
1. 先执行 ./scripts/iisp agent context --json 与 iisp tool list
2. 只使用已注册 tool_id；接线写在 YAML 中文注释（入参← / 出参→）
3. 新 Flow 参照 iisp-catalog/pipelines/kestra/closed_loop_demo_smoke.yaml
4. 写完必须 iisp workflow validate <path>
5. 生产：只提交 YAML，不直接 invoke；dev：可用 iisp tool invoke 串链验证
```

---

## 8. 与「每个工具都是 CLI」的关系

| 层 | 形态 |
|----|------|
| 工具实现 | `tools/<id>/cli.py` 或 `iisp tool invoke` |
| 编排 | YAML 里每步 = 一次 invoke；或 shell 直接 invoke |
| 调度 | Kestra（可选）；不是第二个业务运行时 |
| Agent | 设计态写文件 + validate；运行态触发 Kestra 或 dev shell |

**关键**：Agent 不需要懂 Kestra 语法细节，只需懂 **tool 清单 + params 接线**；`iisp-compose-flow` Skill 负责落成 Kestra YAML。

---

## 相关

- [`FLOW_USER_GUIDE.md`](./FLOW_USER_GUIDE.md) — 人怎么用 Shell
- [`FLOW_YAML_COMMENTS.md`](./FLOW_YAML_COMMENTS.md) — YAML 注释规范
- [`AGENTS.md`](../AGENTS.md) — 设计态 vs 运行态边界
