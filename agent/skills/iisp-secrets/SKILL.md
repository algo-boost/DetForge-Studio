---
name: iisp-secrets
description: >-
  Prevents hardcoded secrets in IISP code, Catalog YAML, and Tool manifests.
  Use when generating config, pipelines, tools, env examples, or any file that
  might contain passwords, tokens, API keys, or connection strings.
---

# IISP 密钥与敏感信息

## 禁止

- 在 **Git 跟踪文件** 中写明文：`password`、`api_key`、`secret`、`token=`（测试假数据除外且须标注 `example-only`）
- 在 `iisp-catalog/pipelines/*.yaml` 写数据库密码、Magic-Fox token
- 在 `tool.manifest.json` 写凭据
- 在 PR 中提交 `config.json`、`.config.key`
- 在日志/print 输出完整 token

## 正确做法

| 场景 | 做法 |
|------|------|
| 平台 API 鉴权 | `config.api_token`，设置页保存，自动 `enc:v1:` |
| Pipeline 参数 | `{{env.VAR_NAME}}` 或运行时 config，**不进 Catalog 明文** |
| Magic-Fox / DB | `config.json` 加密字段 |
| 示例文档 | 用 `YOUR_TOKEN_HERE`、`changeme` |

## 生成 Token（给运维，不写进代码）

```bash
openssl rand -hex 32
```

写入 `/config` 设置页，不要写入源码。

## 校验

- Catalog PR：人工确认无 `enc:` 以外长随机串误用
- 推荐 CI：`gitleaks detect`

## 参考

[`docs/SECURITY.md`](../../docs/SECURITY.md) · [`CONFIG_README.md`](../../CONFIG_README.md)
