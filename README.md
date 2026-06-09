# IISP — 工业检测解决方案平台

**IISP**（**I**ndustrial **I**nspection **S**olutions **P**latform）— 查询筛选、训练平台同步、在线/批量预测、人工质检、筛选归档、评测流水线与 COCO/CSV 导出。

> **产品名**：IISP（工业检测解决方案平台）  
> **代码仓库**：`DetForge-Studio`（历史目录名，与本仓库一致）  
> **最终设计**：[`docs/IISP_DESIGN_FINAL.md`](docs/IISP_DESIGN_FINAL.md)  
> **安全 / Token**：[`docs/SECURITY.md`](docs/SECURITY.md)  
> **产品设计**：[`docs/PRODUCT_DESIGN.md`](docs/PRODUCT_DESIGN.md)  
> **架构图**：[`docs/ARCHITECTURE_DIAGRAMS.md`](docs/ARCHITECTURE_DIAGRAMS.md)  
> **Vibe / Agent**：[`AGENTS.md`](AGENTS.md) · [`.cursor/skills/`](.cursor/skills/)  
> **平台速查**：[`docs/IISP_PLATFORM.md`](docs/IISP_PLATFORM.md)  
> **UI 改造清单**：[`docs/UI_REDESIGN_CHECKLIST.md`](docs/UI_REDESIGN_CHECKLIST.md)  
> **架构文档**：[`docs/ARCHITECTURE_GREENFIELD.md`](docs/ARCHITECTURE_GREENFIELD.md) · [`docs/ARCHITECTURE_DECOUPLED.md`](docs/ARCHITECTURE_DECOUPLED.md)  
> **工具箱与编排**：[`docs/TOOLBOX_ORCHESTRATION.md`](docs/TOOLBOX_ORCHESTRATION.md) · [`docs/CATALOG_CENTER.md`](docs/CATALOG_CENTER.md) · [`docs/SKILL_TO_TOOL.md`](docs/SKILL_TO_TOOL.md)

## 安装与运行

```bash
# 克隆后初始化子模块（看图、预测）
git submodule update --init --recursive
# 或: ./scripts/bootstrap-submodules.sh

pip install -r requirements.txt
cd frontend && npm install && npm run build && cd ..
python app.py
# http://localhost:5050
```

开发模式：`python app.py` + `cd frontend && npm run dev`（5173 代理 API）。

**快速演示编排**：

```bash
./scripts/iisp flow run welcome_demo --reviewer 用户 --auto-resume
# Web: http://127.0.0.1:5173/demo
```

Windows 开发（热重载 + 前端 watch）：

```powershell
.\scripts\dev.ps1
.\scripts\restart.ps1                # 仅重启后端
.\scripts\restart.ps1 -Full          # 重新编译前端并重启
```

## 子模块（packages/，git 分别管理）

| 目录 | 仓库 | 平台集成 |
|------|------|----------|
| [`packages/coco-visualizer`](packages/coco-visualizer/) | COCOVisualizer | 挂载 `/viz`，侧栏「样本图库」 |
| [`packages/detunify`](packages/detunify/) | DetUnify-Studio | 挂载 `/unify`，侧栏「在线预测」 |

详见 [`packages/README.md`](packages/README.md)。  
主仓 `studio/` 内模块（查询、质检、归档、同步、编排）将逐步迁入 `packages/` 并独立 git。

## 用户文档

- 完整手册：[`docs/USER_GUIDE.md`](docs/USER_GUIDE.md)
- 配置说明：[`CONFIG_README.md`](CONFIG_README.md)
- 应用内：侧栏 **帮助 → 使用手册**

## 架构（当前）

```
DetForge-Studio/                 # IISP 主仓库
├── app.py                       # 平台入口 + Tool Gateway
├── capabilities/                # Tool Registry、Manifest
├── orchestration/               # flow_runner、catalog_sync、catalog_providers
├── iisp-catalog/                # Catalog 演示树（生产建议独立 Git 仓）
├── packages/                    # git submodule + platform 共享层
├── studio/                      # 领域能力（查询、质检、forge…）
├── frontend/                    # React 19 + Vite 6（非 umi；暂不做 Electron）
└── docs/IISP_PLATFORM.md        # 平台完整说明（Edge/Hub、Catalog、前端栈）
```

**编排**：

| 档位 | 方式 |
|------|------|
| **Edge**（产线旁、轻量） | `cron` + `iisp flow run`，读 Catalog Pipeline YAML |
| **Hub**（多 Flow、共建） | 可选 [Kestra](https://kestra.io) / Windmill，HTTP 调 Tool |

配置源：Git `iisp-catalog`（默认 GitHub，可迁内网 Git / local Provider）。详见 [`docs/CATALOG_CENTER.md`](docs/CATALOG_CENTER.md)。

遗留 `workflow_engine` 处于迁移期；新流程请写入 Catalog `pipelines/`。

## 配置与安全

在 **设置**（`/config`）配置数据库、图片路径、Magic-Fox、DetUnify 预测环境等。

子模块路径默认自动解析为 `packages/coco-visualizer`、`packages/detunify`；也可在配置中显式填写 `coco_visualizer_root`、`detunify_studio_root`。

敏感字段加密见 `CONFIG_README.md`。**勿提交** `config.json`、`.config.key`、`exports/`、`uploads/`、`datasets/`。

## 侧栏导航

| 分组 | 菜单 |
|------|------|
| **数据查询** | 查询 · 查询结果 · 查询历史 · 查询策略 |
| **质检归档** | 人工质检 · 筛选归档 · 工作流编排 |
| **预测评估** | 在线预测 · 预测任务 · 模型 |
| **平台工具** | 训练平台 · 样本图库 |
| **帮助** | 使用手册 · 设置 |

## 测试

```bash
python -m pytest tests/ -q
```

## Windows 打包

```powershell
cd frontend; npm run build; cd ..
.\packaging\build.ps1
```

发行包需捆绑 `packages/coco-visualizer` 与 `packages/detunify`（或 `tools/` 下同名目录）。批量预测通过 DetUnify 子进程，配置 `predict_python_executable`。
