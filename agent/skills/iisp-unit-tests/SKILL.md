---
name: iisp-unit-tests
description: >-
  Mandatory unit tests for every feature implementation in DetForge-Studio.
  Use when adding or changing backend logic, API routes, Gateway, CLI, Registry,
  orchestration, or Tool service code — tests must ship in the same PR as the feature.
---

# IISP 单元测试（团队强制）

**原则**：**每实现一个功能，必须在同一 PR 内编写并通过单元测试。** 无测试的功能 PR 不得合并。

适用 **全体开发者**（含 Vibe Coding / Agent 生成代码）。审查依据：**iisp-review-pr**。

## 何时必须写测试

| 变更类型 | 最低要求 |
|----------|----------|
| 新 API 路由 / Gateway | Flask `test_client` 冒烟 + 关键分支 |
| 新 Tool / Capability | `invoke` 契约 + 核心 `service` 逻辑（可 mock DB） |
| CLI 子命令 | 参数解析 + 成功/失败退出码或输出 |
| Registry / loader / sync | 发现、校验、边界输入 |
| Bug 修复 | **先写复现测试**，再修代码（Karpathy Goal-Driven） |
| 纯文档 / 注释 / 样式 | 可不新增测试（PR 注明） |

## 何时可以不写

- 仅改 Markdown / 静态资源且行为不变  
- 配置样例、`.env.example`  
- PR 描述明确「无运行时代码变更」  

**有疑问时默认要写。**

## 放哪里

| 代码位置 | 测试位置 |
|----------|----------|
| `server/`、`capabilities/`、`orchestration/`、`cli/` | `tests/test_<模块>.py` |
| `tools/<id>/` | `tools/<id>/tests/` 或 `tests/test_<id>.py` |
| 与现有文件对应 | 参考 [`tests/test_gateway_workbench.py`](../../tests/test_gateway_workbench.py) |

命名：`test_<行为>_<场景>`，例如 `test_v1_invoke_unknown_tool`。

## 怎么写（团队标准）

1. **测行为，不测实现细节** — 公开 API / HTTP / CLI 输出为准  
2. **可 mock 外部依赖** — MySQL、COS、Magic-Fox 等用 `unittest.mock` / `pytest.fixture`  
3. **禁止无意义断言** — 不断言恒真、只测 trivial getter  
4. **与功能同 PR** — 不允许「后续补测试」作为合并条件  
5. **本地必绿** — 提交前运行下方命令  

### 后端示例（Flask Gateway）

```python
def test_v1_invoke_contract_shape(app_client):
    r = app_client.post(
        '/v1/tools/gate-human/invoke',
        data=json.dumps({'run_id': 't', 'step_id': 'g', 'params': {}, 'inputs': {}}),
        content_type='application/json',
    )
    assert r.status_code == 200
    body = r.get_json()
    assert set(body.keys()) == {'status', 'outputs', 'artifacts', 'error'}
```

Fixture 模式见 [`tests/test_gateway_workbench.py`](../../tests/test_gateway_workbench.py)。

## 必跑命令

```bash
# 全量（CI 等价）
python -m pytest tests/ -q

# 仅本次改动相关
python -m pytest tests/test_gateway_workbench.py tests/test_capabilities_registry.py -q
```

Tool 专项：

```bash
./scripts/iisp tool validate tools/<id>/tool.manifest.json
python -m pytest tools/<id>/tests/ -q
```

## 与其它 Skill 的关系

| Skill | 关系 |
|-------|------|
| **iisp-vibe-guardrails** | 开发前自检第 7 条：功能是否已有测试 |
| **iisp-review-pr** | 无测试 → **需修改**，不得 approve |
| **karpathy-guidelines** | 「Fix the bug → 先写复现测试」 |
| **iisp-create-tool** | 步骤 5 校验含 pytest |

## PR 自检清单

- [ ] 新/改逻辑有对应 `test_*.py`  
- [ ] `python -m pytest <paths> -q` 已通过（贴输出或 CI 绿）  
- [ ] 测试覆盖 happy path + 至少一个失败/边界 case（适用时）  
- [ ] 未删除既有测试来「凑绿」  

## 审查话术（iisp-review-pr）

> 缺少与功能同 PR 的单元测试 → **结论：需修改**
