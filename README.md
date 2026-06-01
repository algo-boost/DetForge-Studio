# DefectLoop Studio

**工业缺陷检测数据闭环系统** — 查询筛选、训练平台同步、在线/批量预测、人工质检、COCO/CSV 导出。

> **产品名**：DefectLoop Studio  
> **代码目录名**：`DetForge-Studio`（Git submodule）  
> **产品文档入口**：[`../picture-collection/README.md`](../picture-collection/README.md)

## 安装与运行

```bash
cd tools/DetForge-Studio
pip install -r requirements.txt

cd frontend && npm install && npm run build && cd ..
python app.py
# http://localhost:5050
```

开发模式：`python app.py` + `cd frontend && npm run dev`（5173 代理 API）。

## 集成组件

| 组件 | 挂载 | 入口 |
|------|------|------|
| COCOVisualizer | `/viz` | 侧栏「样本图库」 |
| DetUnify-Studio | `/unify` | 侧栏「在线预测」 |
| Magic-Fox API | 内置 `studio/sync/vendor/` | 侧栏「训练平台」 |


## 用户文档

- 完整手册：[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)
- 配置说明：[`CONFIG_README.md`](CONFIG_README.md)
- 应用内：**设置 → 使用手册**

## 架构

```
DetForge-Studio/
├── app.py                 # 入口
├── worker.py              # 后台作业
├── server/                # Flask（factory、routes、viz/unify 挂载）
├── studio/
│   ├── flow/              # 策略编译
│   ├── query/             # 查询筛选
│   ├── sync/              # Magic-Fox 同步（vendor 脚本）
│   ├── export/            # COCO/CSV
│   └── forge/             # 预测、质检、写库
├── frontend/              # React + Vite
├── docs/                  # 用户手册
├── strategies/            # 策略 JSON
├── config.json            # 本地配置（gitignore，敏感字段加密）
└── .config.key            # 配置密钥（gitignore）
```

## 配置与安全

在 **设置**（`/config`）配置数据库、图片路径、Magic-Fox、DetUnify 预测环境等。

**敏感字段加密**（保存时自动）：`db_password`、`magic_fox_password`、`magic_fox_access_token`、`api_token` → `enc:v1:...` 写入 `config.json`，密钥在 `.config.key`。

依赖：`cryptography`（见 `requirements.txt`）。

**勿提交 git**：`config.json`、`.config.key`、`exports/`、`uploads/`、`datasets/`。

## 侧栏导航（当前）

侧栏按场景分组；查询页 / 预测相关页顶部另有 **SceneHub** 快捷切换。

| 分组 | 菜单 |
|------|------|
| **数据查询** | 查询 · 查询历史 |
| **预测评估** | 在线预测 · 预测任务 · 模型 |
| **平台工具** | 训练平台 · 人工质检 · 样本图库 |
| **设置** | 侧栏底部 |

首次配置可复制 `config.json.example` 为 `config.json` 后编辑，或在 **设置** 页填写。

## 测试

```bash
python -m pytest tests/ -q
```

## Windows 打包

```powershell
cd frontend; npm run build; cd ..
.\packaging\build.ps1
```

预测仍走外部 Python：设置页 `detunify_studio_root` + `predict_python_executable`。
