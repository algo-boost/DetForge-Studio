"""编排参数中英文对照（表单可读性）"""
from __future__ import annotations

# key -> (中文名, 说明)
PARAM_LABELS: dict[str, tuple[str, str]] = {
    'action': ('操作', '工具要执行的动作类型'),
    'task_id': ('查询任务 ID', '查询步骤返回的任务标识，后续批次/导出会引用'),
    'batch_id': ('筛选批次 ID', '创建批次后生成的批次标识，贯穿导出/导入/归档'),
    'batch_code': ('批次编码', '批次的可读编码'),
    'row_count': ('样本行数', '查询结果包含的数据条数'),
    'count': ('计数', '结果数量统计'),
    'strategy_id': ('策略 ID', '捞图或查询策略标识'),
    'strategy_name': ('策略名称', '策略的可读名称'),
    'time_window': ('时间窗', '查询或捞图的时间范围'),
    'reviewer': ('复核人', '负责筛选复核的人员'),
    'intent_type': ('意图类型', '创建批次时的业务意图分类'),
    'data_source': ('数据源', '查询使用的数据来源（detail / predict_result）'),
    'model_id': ('模型 ID', '预测使用的模型标识（forge 注册表）'),
    'train_id': ('训练模型 ID', '平台训练产出的模型标识'),
    'threshold': ('置信度阈值', '预测保留框的最小置信度'),
    'device': ('推理设备', '预测运行设备，如 cuda:0 / cpu'),
    'recall_strategy_id': ('二次查询策略 ID', '在预测结果上二次筛选所用策略'),
    'predict_job_id': ('预测作业 ID', '二次查询引用的预测作业，用于读取 predict_result'),
    'job_id': ('作业 ID', '异步预测作业标识'),
    'export_dir': ('导出目录', '出站包写入的目录路径'),
    'archive_dir': ('归档目录', '归档结果写入的目录'),
    'items': ('导出条目', '导出包内的数据条目'),
    'keep_count': ('保留数量', '筛选后保留的样本数'),
    'event': ('通知事件', '通知类型或事件名'),
    'gate_type': ('卡点类型', '人工卡点等待的操作类型'),
    'waiting': ('等待状态', '是否处于等待人工处理'),
    'notify_on_empty': ('空结果通知', '查询无结果时是否仍发送通知'),
    'upstream': ('上游输出包', '上一步工具返回的 outputs，供本步引用'),
    'run_id': ('运行 ID', '本次编排执行的唯一标识'),
    'step_id': ('步骤 ID', '当前步骤在 Flow 中的标识'),
}

OUTPUT_LABELS: dict[str, tuple[str, str]] = {
    'task_id': ('查询任务 ID', '供创建批次等后续步骤使用'),
    'batch_id': ('筛选批次 ID', '供导出、导入、归档与人工卡点使用'),
    'row_count': ('样本行数', '查询产出的数据量'),
    'export_dir': ('导出目录', '人工编辑 COCO 的出站目录'),
    'event': ('通知事件', '流程结束或卡点触发的通知'),
    'job_id': ('预测作业 ID', '批量预测异步作业标识'),
    'total': ('预测总数', '预测作业的图片/样本总量'),
    'done': ('已完成数', '预测作业已处理的数量'),
    'status': ('状态', '工具执行状态'),
}


def param_title(key: str) -> str:
    if key in PARAM_LABELS:
        return PARAM_LABELS[key][0]
    return key.replace('_', ' ')


def param_description(key: str, *, fallback: str = '') -> str:
    if key in PARAM_LABELS:
        return PARAM_LABELS[key][1]
    return fallback


def output_title(key: str) -> str:
    if key in OUTPUT_LABELS:
        return OUTPUT_LABELS[key][0]
    return param_title(key)


def output_description(key: str, *, fallback: str = '') -> str:
    if key in OUTPUT_LABELS:
        return OUTPUT_LABELS[key][1]
    return fallback or param_description(key)
