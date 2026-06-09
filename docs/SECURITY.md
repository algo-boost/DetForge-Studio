# IISP 安全与 Token 管理

**版本**：v1.0  
**日期**：2026-06-09  
**状态**：定稿（现状说明 + 目标方案 + 实施路线）  
**关联**：[`IISP_DESIGN_FINAL.md`](./IISP_DESIGN_FINAL.md) · [`CONFIG_README.md`](../CONFIG_README.md) · [`PLATFORM_RISK_REGISTER.md`](./PLATFORM_RISK_REGISTER.md)

---

## 1. 安全模型总览

IISP 分 **三档** 安全需求，不可混为一谈：

| 档位 | 场景 | 身份模型 | 目标 |
|------|------|----------|------|
| **Edge 产线** | 内网单机、固定工位 | 共享 **Service Token** + 网络隔离 | 防误连公网、防内网误访问 |
| **Hub 协作** | 多团队、共建 Catalog | **OIDC 用户** + 角色 RBAC | 谁改了什么可审计 |
| **机器调用** | Kestra、cron、MCP、CLI | **Scoped Token** / mTLS（可选） | 编排器仅能 invoke，不能改配置 |

**现状**：仅 Edge 档中的 **可选单 Token + 配置加密** 已实现；登录、RBAC、Token 生命周期管理 **未实现**。

---

## 2. Token 分类（必须区分）

| 类型 | 用途 | 现状 | 目标 |
|------|------|------|------|
| **T1 Service API Token** | 浏览器/脚本调 `/api/*` | `config.api_token` 单密钥 | 可轮换、可吊销、分环境 |
| **T2 User Session** | 登录用户身份 | ❌ 无 | OIDC → JWT / Session（Hub） |
| **T3 Orchestration Token** | Kestra → Gateway invoke | ❌ 无独立 | 专用 `kestra` scope，仅 invoke |
| **T4 Resume Token** | 人工卡点后继续 Flow | 内存/demo 文件 | 短 TTL + 单次使用 + HMAC |
| **T5 MCP Dev Token** | Cursor MCP 调 validate/list | ❌ 未实现 | 仅 dev，禁止生产 invoke |
| **T6 Webhook Secret** | n8n/Kestra 回调验签 | ❌ 无 | HMAC 签名头 |
| **T7 Config Secrets** | DB/Magic-Fox 密码 | ✅ Fernet 加密 | 保持 + 密钥轮换手册 |

**禁止**：所有能力共用一个 `api_token` 且无 scope（现状风险）。

---

## 3. 现状：已实现

### 3.1 可选 API Token（T1 雏形）

- 配置：`config.json` → `api_token`（非空才启用）  
- 校验：`server/factory.py` → `/api/`、`/viz/api/`  
- 传递：`X-API-Token` 或 `?token=`  
- 前端：`localStorage.pc_api_token` + `client.js`  

**默认关闭**：`api_token` 为空 = **无鉴权**。

### 3.2 配置落盘加密

- `studio/config_crypto.py`：Fernet，`enc:v1:`  
- 敏感键：`db_password`、`magic_fox_*`、`api_token`  
- 密钥：`.config.key` 或 `DEFECTLOOP_CONFIG_KEY`  

详见 [`CONFIG_README.md`](../CONFIG_README.md)。

---

## 4. 现状：主要风险

| # | 风险 | 严重度 | 说明 |
|---|------|--------|------|
| R1 | 默认无鉴权 | 高 | 未配 token 时 API 全开放 |
| R2 | 单 Token 全员共享 | 高 | 泄露无法定位责任人 |
| R3 | Token 在 URL  query | 中 | `?token=` 进日志、Referer、浏览器历史 |
| R4 | localStorage 存 Token | 中 | XSS 可读 |
| R5 | SPA 不鉴权 | 中 | 仅 API 拦截，页面仍可打开 |
| R6 | 无轮换/吊销 | 中 | 泄露只能改 config 重启 |
| R7 | 无审计日志 | 中 | 不知谁调了 invoke |
| R8 | 子应用 viz/unify | 中 | Token 传播不一致 |
| R9 | Catalog Git 误提交密钥 | 高 | Pipeline 里写 password |
| R10 | Agent/MCP 生产 invoke | 高 | 文档禁止，代码未强制 |

---

## 5. Token 管理目标方案

### 5.1 T1 Service API Token（Edge + 过渡期 Hub）

**管理原则**：

1. **一环境一 Token**（dev/staging/prod 不同）  
2. **禁止提交 Git**；仅 `config.json` + 加密落盘  
3. **轮换周期**：生产 ≤ 90 天，泄露即换  
4. **传输优先 Header**；`?token=` 仅保留给 `<img>` 等无法带头部的遗留路径，新 API 禁止 query token  
5. **日志脱敏**：access log 不打印 token；错误信息不 echo 完整 token  

**运维流程**：

```text
1. 生成：openssl rand -hex 32
2. 写入：设置页 /config 保存 api_token（自动加密）
3. 分发：运维通道发给工位浏览器（设置页「客户端 Token」一次写入 sessionStorage 或 httpOnly cookie——见 S2）
4. 轮换：新 token 写入 → 通知用户更新 → 旧 token 宽限期 24h → 移除旧值
5. 泄露：立即轮换 + 查 access 日志（S4 后）
```

**配置项（规划扩展）**：

```json
{
  "api_token": "enc:v1:...",
  "api_token_prev": "enc:v1:...",
  "api_token_prev_expires_at": "2026-06-10T00:00:00Z"
}
```

校验逻辑：接受 `api_token` 或宽限期内的 `api_token_prev`。

### 5.2 T2 用户登录（Hub，M5）

| 项 | 选型 |
|----|------|
| 协议 | **OIDC**（飞书 / Keycloak / Authentik） |
| 会话 | **HttpOnly Secure Cookie** 或 BFF 发短期 JWT |
| 前端 | 未登录 → `/login` → 回调；API 用 Cookie，**不再** localStorage 存长期密钥 |
| 角色 | IdP groups → `qc` / `algo` / `ops` / `admin` |

Edge **可不部署登录**，继续 T1 + 内网隔离。

### 5.3 T3 编排专用 Token

- Gateway 支持 **`X-API-Token` + scope**（或独立 header `X-IISP-Scope: invoke`）  
- Kestra Flow 环境变量注入 **只读 invoke token**，不能调 `/api/config`  
- 与浏览器 Service Token **分离**

### 5.4 T4 Resume Token

- 生成：`secrets.token_urlsafe(32)`  
- 存储：detforge 或 Redis，字段 `expires_at`、`run_id`、`used`  
- 校验：单次使用、TTL 默认 72h、绑定 `run_id`  
- **禁止**可猜测的递增 id  

### 5.5 T5 MCP / Agent

| 环境 | 策略 |
|------|------|
| dev | MCP 可 list/validate；`IISP_AGENT_ALLOW_INVOKE=0` 默认 |
| prod | 不暴露 MCP；或只读 + 网络 localhost |

### 5.6 T6 Webhook

- `POST /v1/orchestration/resume` 要求 `X-IISP-Signature: hmac-sha256(body, webhook_secret)`  
- `webhook_secret` 进 config 加密，不进 Catalog Git  

---

## 6. 密钥与 Catalog 规范

### 6.1 Git 与 Pipeline

**禁止**在以下位置出现明文密钥：

- `iisp-catalog/pipelines/*.yaml`  
- `strategies/*.json`  
- `tool.manifest.json`  

使用：

```yaml
params:
  strategy_id: daily_trawl
  # 敏感项用环境占位，运行时从 config / env 注入
  notify_webhook: "{{env.IISP_N8N_WEBHOOK_URL}}"
```

CI 增加 **gitleaks** 或自定义规则扫描 `password|secret|token=`。

### 6.2 Vibe Coding

Skill 约束：`.cursor/skills/iisp-secrets`（见仓库）— Agent 不得生成硬编码密钥。

---

## 7. 网络与传输

| 项 | Edge | Hub |
|----|------|-----|
| TLS | 反向代理 HTTPS | 必须 HTTPS |
| 绑定 | `127.0.0.1` 或内网 IP | 内网 + 网关 |
| CORS | 生产关闭 `PC_DEV_CORS` | 白名单源 |
| 上传大小 | 已有 `PC_MAX_CONTENT_MB` | 按角色限流（规划） |

---

## 8. 审计与合规（规划）

| 事件 | 记录 |
|------|------|
| invoke 失败/成功 | `run_id`, `tool_id`, `step_id`, 耗时（**无** token） |
| config 变更 | 谁、何时、改了哪些 key（**不**记录 secret 值） |
| catalog sync | commit、操作者（机器账号） |
| login/logout | Hub OIDC sub、角色 |

存储：detforge `audit_log` 表或 JSONL；保留期可配置。

---

## 9. 实施路线（Security S1–S5）

| 阶段 | 交付 | 依赖 |
|------|------|------|
| **S1** | 文档 + 生产检查清单；设置页 **API Token** 字段与 **401 引导**；`config.json.example` 注释 | 小 |
| **S2** | **双 Token 宽限期**轮换；禁止新 API 使用 query token；日志脱敏 | M1 Gateway |
| **S3** | **Scoped tokens**：`invoke` / `admin` scope；Kestra 专用 token | M1 |
| **S4** | **审计日志** invoke + config 变更 | M2 |
| **S5** | **OIDC 登录** + RBAC + HttpOnly 会话 | M5 |

**立即（无代码）**：生产必须设 `api_token` + HTTPS + 内网；备份 `.config.key` 与 config。

---

## 10. 生产检查清单

- [ ] `api_token` 已设置且非默认值  
- [ ] `config.json`、`.config.key` 未进 Git  
- [ ] `pip install cryptography` 已安装  
- [ ] 服务仅内网或 HTTPS 反向代理  
- [ ] `PC_DEV_CORS` 未在生产开启  
- [ ] Magic-Fox / DB 密码为 `enc:v1:` 格式  
- [ ] Catalog 仓已配 gitleaks / secret scan  
- [ ] Kestra/n8n webhook 使用独立 secret（S6 前勿暴露公网 callback）  
- [ ] 备份：`config.json` + `.config.key` + detforge  

---

## 11. 修订记录

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2026-06-09 | Token 分类、现状风险、目标方案、S1–S5 |
