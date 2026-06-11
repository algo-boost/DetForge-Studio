# Query 工具 UI

## 两种使用方式

### 1. IISP 集成（默认，最快）

Shell 内 **直接 lazy 加载** Query 页面（`QueryToolHost`），共享 Layout、导航、React 树，**无 iframe**。

config 默认 `"query_tool": { "integration": "embedded" }`。

### 2. 独立部署

```bash
bash scripts/query-standalone.sh
# 或 SKIP_QUERY_UI_BUILD=1 bash scripts/query-standalone.sh
```

- 地址：`http://127.0.0.1:6021/`
- 含：UI + `/api/query*` + `/api/strategies*` + `/v1/tools/query/invoke`

### 3. 远程 iframe 集成

IISP `config.json`：

```json
{
  "query_tool": {
    "integration": "remote",
    "remote_url": "http://127.0.0.1:6021"
  }
}
```

Shell 通过 iframe 连接独立 Query 服务（适用于跨机/隔离部署）。

## 构建

```bash
bash tools/query/ui/build.sh
```

同进程挂载（书签/直连）：`http://127.0.0.1:5050/tools/query/#/query`

## 目录

```
tools/query/ui/
├── frontend/     # Vite（@iisp 别名 → Shell 源码，仅 standalone 构建用）
├── templates/
├── static/dist/
└── build.sh
```
