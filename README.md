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

Windows 开发（热重载 + 前端 watch）：

```powershell
.\scripts\dev.ps1                    # 长期开发（前端 watch + Flask 热重载）
.\scripts\restart.ps1                # 仅重启后端（最快，不编译前端）
.\scripts\restart.ps1 -Full          # 前端 npm run build + 重启（改 UI 后必用）
.\scripts\restart.ps1 -RebuildFrontend   # 同 -Full
```

也可双击（`scripts/` 目录下）：

| 脚本 | 作用 |
|------|------|
| `restart.bat` | 只重启后端 |
| `restart-full.bat` | 重新编译前端并重启 |

Python 路径：`$env:PC_PYTHON` 或复制 `scripts/dev.local.ps1.example` → `scripts/dev.local.ps1`。

## 集成组件

| 组件 | 挂载 | 入口 |
|------|------|------|
| COCOVisualizer | `/viz` | 侧栏「样本图库」 |
| DetUnify-Studio | `/unify` | 侧栏「在线预测」 |
| Magic-Fox API | 内置 `studio/sync/vendor/` | 侧栏「训练平台」 |


## 用户文档

- 完整手册：[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)
- 配置说明：[`CONFIG_README.md`](CONFIG_README.md)
- 应用内：侧栏底部 **帮助 → 使用手册**

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
| **数据查询** | 查询 · 查询历史 · 查询策略 |
| **质检归档** | 人工质检 · 筛选归档 |
| **预测评估** | 在线预测 · 预测任务 · 模型 |
| **平台工具** | 训练平台 · 样本图库 |
| **帮助**（侧栏底部） | 使用手册 · 设置 |

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

产物：`dist/DefectLoop-Studio/`（含 `DefectLoop-Studio.exe`）与 `dist/DefectLoop-Studio-win-<version>.zip`。

发行包内已捆绑：

| 目录 | 用途 |
|------|------|
| `tools/COCOVisualizer` | 样本图库（`/viz` 同进程挂载） |
| `tools/DetUnify-Studio` | 在线预测 UI（`/unify`）与批量预测脚本 |

**批量预测**仍通过外部 Python 子进程执行（含 torch/mmdet），在 `config.json` 设置 `predict_python_executable`（如 Magic-Fox 环境的 `python.exe`）。默认脚本路径：`tools/DetUnify-Studio/scripts/predict_job_worker.py`。

首次解压后编辑同目录 `config.json`（或由 `config.json.example` 复制），填写数据库与预测 Python 路径后运行 `Start-DefectLoop.bat`，访问 `http://127.0.0.1:5050`。
