"""内置工作流模板定义与种子数据。"""
from __future__ import annotations

from studio.forge import forge_db

BUILTIN_TEMPLATES = [
    {
        'id': 'daily_ng_curation',
        'name': '每日捞图 · 出站筛选归档',
        'description': '查询筛选 NG 样本 → 创建筛选批次 → 导出出站包 → 等待上传 COCO → 导入 → 归档',
        'version': 1,
        'builtin': 1,
        'definition': {
            'params_schema': {
                'strategy_id': {'type': 'strategy', 'default': 'daily_trawl', 'label': '捞图策略'},
                'time_window': {'type': 'time_window', 'default': {'preset': 'yesterday'}},
                'reviewer': {'type': 'string', 'label': '复核人'},
            },
            'steps': [
                {
                    'id': 'query',
                    'kind': 'query',
                    'params': {
                        'strategy_id': '{{params.strategy_id}}',
                        'time_window': '{{params.time_window}}',
                        'data_source': 'detail',
                    },
                },
                {
                    'id': 'batch',
                    'kind': 'curation_create',
                    'requires': ['query'],
                    'params': {
                        'task_id': '{{steps.query.task_id}}',
                        'intent_type': 'daily_ng',
                        'reviewer': '{{params.reviewer}}',
                    },
                },
                {
                    'id': 'export',
                    'kind': 'curation_export',
                    'requires': ['batch'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'human_edit',
                    'kind': 'gate_human',
                    'requires': ['export'],
                    'params': {
                        'gate_type': 'curation_coco_edit',
                        'batch_id': '{{steps.batch.batch_id}}',
                        'instructions': '请用 COCO 工具编辑出站包，完成后在编排控制台点击「继续」或在筛选归档页上传 COCO',
                    },
                },
                {
                    'id': 'import',
                    'kind': 'curation_import',
                    'requires': ['human_edit'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'archive',
                    'kind': 'curation_archive',
                    'requires': ['import'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'notify',
                    'kind': 'notify',
                    'params': {'event': 'workflow_done'},
                },
            ],
        },
    },
    {
        'id': 'weekly_predict_eval',
        'name': '每周预测评测 · 出站筛选归档',
        'description': 'Stage1 捞图 → 预测 → 误检评测筛选 → 出站 → 上传 COCO → 归档',
        'version': 1,
        'builtin': 1,
        'definition': {
            'params_schema': {
                'stage1_strategy_id': {'type': 'strategy', 'default': 'daily_trawl', 'label': 'Stage1 捞图策略'},
                'stage2_strategy_id': {'type': 'strategy', 'default': 'fp_eval_set', 'label': 'Stage2 评测策略'},
                'model_id': {'type': 'model', 'required': True, 'label': '预测模型'},
                'time_window': {'type': 'time_window', 'default': {'preset': 'last_7d'}},
                'threshold': {'type': 'number', 'default': 0.1},
                'reviewer': {'type': 'string', 'label': '复核人'},
            },
            'steps': [
                {
                    'id': 'query_s1',
                    'kind': 'query',
                    'params': {
                        'strategy_id': '{{params.stage1_strategy_id}}',
                        'time_window': '{{params.time_window}}',
                        'data_source': 'detail',
                    },
                },
                {
                    'id': 'predict',
                    'kind': 'predict',
                    'requires': ['query_s1'],
                    'params': {
                        'task_id': '{{steps.query_s1.task_id}}',
                        'model_id': '{{params.model_id}}',
                        'threshold': '{{params.threshold}}',
                    },
                },
                {
                    'id': 'query_s2',
                    'kind': 'query',
                    'requires': ['predict'],
                    'params': {
                        'strategy_id': '{{params.stage2_strategy_id}}',
                        'predict_job_id': '{{steps.predict.job_id}}',
                        'data_source': 'predict_result',
                    },
                },
                {
                    'id': 'batch',
                    'kind': 'curation_create',
                    'requires': ['query_s2'],
                    'params': {
                        'task_id': '{{steps.query_s2.task_id}}',
                        'intent_type': 'replay_eval',
                        'data_source': 'predict_result',
                        'reviewer': '{{params.reviewer}}',
                    },
                },
                {
                    'id': 'export',
                    'kind': 'curation_export',
                    'requires': ['batch'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'human_edit',
                    'kind': 'gate_human',
                    'requires': ['export'],
                    'params': {
                        'gate_type': 'curation_coco_edit',
                        'batch_id': '{{steps.batch.batch_id}}',
                        'instructions': '请编辑误检评测出站包 COCO，完成后上传并继续流程',
                    },
                },
                {
                    'id': 'import',
                    'kind': 'curation_import',
                    'requires': ['human_edit'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'archive',
                    'kind': 'curation_archive',
                    'requires': ['import'],
                    'params': {'batch_id': '{{steps.batch.batch_id}}'},
                },
                {
                    'id': 'notify',
                    'kind': 'notify',
                    'params': {'event': 'workflow_done'},
                },
            ],
        },
    },
]

DEFAULT_SCHEDULES = [
    {
        'template_id': 'daily_ng_curation',
        'name': '每日凌晨捞图出站',
        'cron_expr': '0 2 * * *',
        'params': {'strategy_id': 'daily_trawl', 'time_window': {'preset': 'yesterday'}},
        'notify_policy': {
            'events': {
                'workflow_started': ['ui'],
                'step_skipped': ['ui'],
                'waiting_human': ['ui', 'feishu', 'email'],
                'workflow_done': ['ui', 'feishu'],
                'workflow_failed': ['ui', 'feishu', 'email'],
            },
        },
    },
    {
        'template_id': 'weekly_predict_eval',
        'name': '每周一预测评测',
        'cron_expr': '0 3 * * 1',
        'params': {
            'stage1_strategy_id': 'daily_trawl',
            'stage2_strategy_id': 'fp_eval_set',
            'time_window': {'preset': 'last_7d'},
            'threshold': 0.1,
        },
        'notify_policy': {
            'events': {
                'workflow_started': ['ui'],
                'step_skipped': ['ui'],
                'waiting_human': ['ui', 'feishu', 'email'],
                'workflow_done': ['ui', 'feishu'],
                'workflow_failed': ['ui', 'feishu', 'email'],
            },
        },
    },
]


def ensure_builtin_templates():
    """幂等写入内置模板。"""
    if not forge_db.schema_ready():
        return 0
    n = 0
    for tpl in BUILTIN_TEMPLATES:
        existing = forge_db.get_workflow_template(tpl['id'])
        if not existing:
            forge_db.upsert_workflow_template(tpl)
            n += 1
        elif existing.get('builtin'):
            forge_db.upsert_workflow_template(tpl)
    return n


def ensure_default_schedules():
    """首次无调度时写入示例定时任务（需 params 中 model_id 由用户后续配置）。"""
    if not forge_db.schema_ready():
        return 0
    existing = forge_db.list_workflow_schedules(limit=1)
    if existing:
        return 0
    from studio.forge.workflow_scheduler import compute_next_run

    n = 0
    for spec in DEFAULT_SCHEDULES:
        nra = compute_next_run(spec['cron_expr'], spec.get('timezone'))
        forge_db.create_workflow_schedule({**spec, 'next_run_at': nra, 'enabled': 0})
        n += 1
    return n
