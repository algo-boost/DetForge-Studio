"""内置工作流步骤 Capability 注册。"""
from __future__ import annotations

from capabilities.registry import CapabilityRegistry


def register_builtin_capabilities(registry: CapabilityRegistry) -> None:
    from studio.forge import workflow_steps as ws

    registry.register_function(
        'query', '数据查询',
        ws.run_query_step,
        output_keys=['task_id', 'row_count', 'count', 'data_source'],
        description='按策略查询平台数据并创建查询任务',
    )
    registry.register_function(
        'predict', '批量预测',
        ws.run_predict_step,
        output_keys=['job_id', 'total', 'done', 'status'],
        description='对查询任务发起预测作业并等待完成',
    )
    registry.register_function(
        'curation-create', '创建筛选批次',
        ws.run_curation_create_step,
        output_keys=['batch_id', 'batch_code'],
        description='从查询任务创建筛选归档批次',
    )
    registry.register_function(
        'curation-export', '导出出站包',
        ws.run_curation_export_step,
        output_keys=['batch_id', 'export_dir', 'items'],
        description='导出筛选批次 COCO 出站包',
    )
    registry.register_function(
        'gate-human', '人工卡点',
        ws.run_gate_human_step,
        output_keys=['gate_type', 'batch_id', 'waiting'],
        description='等待人工上传 COCO 或确认',
        waiting_kinds=frozenset({'gate-human'}),
    )
    registry.register_function(
        'curation-import', '导入筛选 COCO',
        ws.run_curation_import_step,
        output_keys=['batch_id', 'status', 'keep_count'],
        description='导入人工编辑后的 COCO',
    )
    registry.register_function(
        'curation-archive', '筛选归档',
        ws.run_curation_archive_step,
        output_keys=['batch_id', 'archive_dir', 'keep_count'],
        description='归档筛选结果',
    )
    registry.register_function(
        'notify', '流程通知',
        ws.run_notify_step,
        output_keys=['event'],
        description='发送工作流完成/卡点通知',
    )

    from capabilities import demo_tools as dt

    registry.register_function(
        'demo-query', '演示 · 模拟捞图查询',
        dt.run_demo_query,
        output_keys=['task_id', 'row_count', 'sample_rows'],
        description='无需数据库，返回模拟查询任务与样本行',
    )
    registry.register_function(
        'demo-pack', '演示 · 模拟出站打包',
        dt.run_demo_pack,
        output_keys=['batch_id', 'batch_code', 'export_dir'],
        description='根据查询任务生成演示批次与导出路径',
    )
    registry.register_function(
        'demo-notify', '演示 · 通知',
        dt.run_demo_notify,
        output_keys=['event', 'message'],
        description='打印演示通知（stdout），不依赖 forge_db',
    )
