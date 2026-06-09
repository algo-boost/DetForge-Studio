# IISP 子模块（packages）

**IISP**（**I**ndustrial **I**nspection **S**olutions **P**latform，工业检测解决方案平台）将各能力以 **Git Submodule** 集成在本仓库 `packages/` 下，逻辑独立、版本分别管理。

## 已集成（独立 git）

| 目录 | 仓库 | 能力 | 单独运行 |
|------|------|------|----------|
| [`coco-visualizer/`](coco-visualizer/) | [algo-boost/COCOVisualizer](https://github.com/algo-boost/COCOVisualizer) | 样本图库、COCO 浏览/改标注 | `cd packages/coco-visualizer && python app.py` → :6010 |
| [`detunify/`](detunify/) | [algo-boost/DetUnify-Studio](https://github.com/algo-boost/DetUnify-Studio) | 多模型预测、临时对比 UI | `cd packages/detunify/app && python app.py` → :6006 |

平台默认通过 **同进程挂载** 使用：`/viz`、`/unify`（见根目录 `python app.py` :5050）。  
路径解析顺序见 [`studio/paths.py`](../studio/paths.py)：`packages/*` → 发行包 `tools/*` → 历史 sibling `../COCOVisualizer`。

## 初始化子模块

```bash
# 在 IISP 仓库根目录（DetForge-Studio）
git submodule update --init --recursive

# 或使用脚本
./scripts/bootstrap-submodules.sh
```

更新某一子模块：

```bash
git submodule update --remote packages/coco-visualizer
git submodule update --remote packages/detunify
```

## 仓内工具包

| 目录 | 说明 |
|------|------|
| [`platform/`](platform/) | 共享 DB、img_path、SN 查询（查询与质检共用） |
| [`yf_door_panel_query/`](yf_door_panel_query/) | Skills→Tool 示范包 |

每个工具包可提供根目录 `tool.manifest.json`，由 `capabilities/registry` 自动发现。

## 规划中的仓内模块（暂在 `studio/`）

以下能力仍在主仓 `studio/` 中，后续可拆为独立 git 并迁入 `packages/`：

| 规划目录 | 现状代码 | 能力 |
|----------|----------|------|
| `platform/` | ✓ 已落地 `packages/platform` | 查询与质检共用平台访问层 |
| `query/` | `studio/query`、`studio/flow` | 数据查询、策略、Flow |
| `curation/` | `studio/curation`、`studio/export` | 筛选归档、导出 |
| `manual-qc/` | `studio/forge/forge_manual_qc` | 人工质检 |
| `predict-job/` | `studio/forge/forge_predict` | 预测作业编排（推理在 detunify） |
| `sync/` | `studio/sync` | Magic-Fox 训练平台同步 |
| `orchestration/` | `studio/forge/workflow_*` | 组合流水线、看板 |
| `contracts/` | 新建 | Capability 契约类型 |

架构说明见 [`docs/ARCHITECTURE_DECOUPLED.md`](../docs/ARCHITECTURE_DECOUPLED.md)。
