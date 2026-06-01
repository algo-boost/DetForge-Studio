"""工作流环境变量：SQL / Python 中的 ${VAR} 占位符解析与注入。"""
from __future__ import annotations

import re
from typing import Any

VAR_PATTERN = re.compile(r'\$\{([A-Z][A-Z0-9_]*)\}')
GET_ENV_PATTERN = re.compile(r"""get_env\s*\(\s*['"]([A-Z][A-Z0-9_]*)['"]""", re.I)
ENV_CALL_PATTERN = re.compile(r"""env\s*\(\s*['"]([A-Z][A-Z0-9_]*)['"]""", re.I)

# 由系统自动注入（非策略「可调参数」）；时段仅 START/END 在工具栏，其余用户参数走 env_schema
SYSTEM_VARS = frozenset({
    'START_TIME',
    'END_TIME',
    'JOB_ID',
    'PREDICT_JOB_ID',
    'DATA_SOURCE',
    'THRESHOLD',
    'MODEL_ID',
    'MODEL_NAME',
    'RUN_ID',
    'STAGE',
})

SYSTEM_VAR_LABELS = {
    'START_TIME': '开始时间',
    'END_TIME': '结束时间',
    'JOB_ID': '预测作业 ID',
    'PREDICT_JOB_ID': '预测作业 ID',
    'DATA_SOURCE': '数据源',
    'THRESHOLD': '预测阈值',
    'MODEL_ID': '模型 ID',
    'MODEL_NAME': '模型名称',
    'RUN_ID': '回跑任务 ID',
    'STAGE': '当前阶段',
}


def normalize_env_dict(raw=None) -> dict[str, str]:
    """将 env / variables 规范为大写键、字符串值。"""
    if not raw:
        return {}
    out = {}
    if isinstance(raw, dict):
        items = raw.items()
    elif isinstance(raw, list):
        items = ((row.get('key'), row.get('value')) for row in raw if isinstance(row, dict))
    else:
        return out
    for key, val in items:
        if key is None:
            continue
        k = str(key).strip().upper()
        if not k:
            continue
        if val is None:
            continue
        s = str(val).strip()
        if s == '':
            continue
        out[k] = s
    return out


def merge_context(*layers: dict | None) -> dict[str, str]:
    merged: dict[str, str] = {}
    for layer in layers:
        if layer:
            merged.update({str(k).upper(): str(v) for k, v in layer.items() if v is not None})
    return merged


def extract_template_vars(*texts: str | None) -> list[str]:
    """从 SQL / Python 模板中提取 ${VAR} 与 get_env('VAR') 引用。"""
    found = set()
    for text in texts:
        if not text:
            continue
        s = str(text)
        found.update(v.upper() for v in VAR_PATTERN.findall(s))
        found.update(v.upper() for v in GET_ENV_PATTERN.findall(s))
        found.update(v.upper() for v in ENV_CALL_PATTERN.findall(s))
    return sorted(found)


def substitute_template(text: str | None, context: dict | None) -> str:
    """将 text 中已知 context 键的 ${VAR} 替换为值；未知占位符保留原样。"""
    if not text:
        return text or ''
    out = str(text)
    ctx = normalize_env_dict(context)
    for key, val in ctx.items():
        out = out.replace(f'${{{key}}}', val)
    return out


def find_unresolved_template_vars(text: str | None) -> list[str]:
    """substitute 后仍残留的 ${VAR}（未注入值的变量）。"""
    if not text:
        return []
    return sorted(set(VAR_PATTERN.findall(str(text))))


def format_unresolved_vars_error(vars_list: list[str], schema: list[dict] | None = None) -> str:
    if not vars_list:
        return ''
    label_map = {
        str(row.get('key', '')).upper(): row.get('label') or row.get('key')
        for row in (schema or [])
    }
    parts = [f"{label_map.get(v, v)}(${v})" for v in vars_list]
    return f"以下变量未设置值，请在「策略参数」中填写：{', '.join(parts)}"


def build_system_context(
    *,
    start_time: str | None = None,
    end_time: str | None = None,
    job_id=None,
    data_source: str | None = None,
    threshold=None,
    model_id=None,
    model_name: str | None = None,
    run_id=None,
    stage: str | None = None,
) -> dict[str, str]:
    ctx: dict[str, str] = {}
    if start_time:
        ctx['START_TIME'] = str(start_time)
    if end_time:
        ctx['END_TIME'] = str(end_time)
    if job_id is not None:
        jid = str(int(job_id))
        ctx['JOB_ID'] = jid
        ctx['PREDICT_JOB_ID'] = jid
    if data_source:
        ctx['DATA_SOURCE'] = str(data_source)
    if threshold is not None and str(threshold).strip() != '':
        ctx['THRESHOLD'] = str(threshold)
    if model_id is not None:
        ctx['MODEL_ID'] = str(int(model_id))
    if model_name:
        ctx['MODEL_NAME'] = str(model_name)
    if run_id is not None:
        ctx['RUN_ID'] = str(int(run_id))
    if stage:
        ctx['STAGE'] = str(stage)
    return ctx


def resolve_strategy_env_schema(strategy: dict | None) -> list[dict[str, Any]]:
    """
    解析策略可配置环境变量 schema。
    优先使用 strategy.env_schema；否则从 SQL/Python 模板推断自定义变量。
    """
    strategy = strategy or {}
    schema = strategy.get('env_schema')
    if isinstance(schema, list) and schema:
        out = []
        for row in schema:
            if not isinstance(row, dict):
                continue
            key = str(row.get('key') or '').strip().upper()
            if not key or key in SYSTEM_VARS:
                continue
            out.append({
                'key': key,
                'label': row.get('label') or key,
                'type': row.get('type') or 'text',
                'default': row.get('default'),
                'placeholder': row.get('placeholder'),
                'stage': row.get('stage'),
                'description': row.get('description'),
            })
        return out

    inferred = [
        v for v in extract_template_vars(
            strategy.get('sql_template'),
            strategy.get('python_code'),
            strategy.get('filter_rules_code'),
            strategy.get('sample_code'),
        )
        if v not in SYSTEM_VARS
    ]
    return [{'key': k, 'label': k, 'type': 'text'} for k in inferred]


def describe_strategy_variables(strategy: dict | None) -> dict[str, Any]:
    """返回策略变量说明（系统 + 自定义 schema）。"""
    strategy = strategy or {}
    schema = resolve_strategy_env_schema(strategy)
    inferred = extract_template_vars(
        strategy.get('sql_template'),
        strategy.get('python_code'),
        strategy.get('filter_rules_code'),
    )
    return {
        'strategy_id': strategy.get('id'),
        'system_vars': [
            {'key': k, 'label': SYSTEM_VAR_LABELS.get(k, k), 'auto': True}
            for k in sorted(SYSTEM_VARS)
        ],
        'custom_vars': schema,
        'template_vars': inferred,
        'user_vars': [row['key'] for row in schema],
    }


def build_stage_context(
    body: dict | None,
    *,
    stage: str | None = None,
    job_id=None,
    predict: dict | None = None,
    run_id=None,
    model_name: str | None = None,
    start_time: str | None = None,
    end_time: str | None = None,
    sample_size=None,
    random_seed=None,
) -> dict[str, str]:
    """合并系统变量 + 全局 env + 阶段 env。"""
    body = body or {}
    predict = predict or body.get('predict') or {}

    ds = 'predict_result' if job_id is not None else None
    if not ds:
        ds = body.get('data_source') or 'detail'

    if sample_size is None and body.get('sample_size') is not None:
        sample_size = body.get('sample_size')
    if random_seed is None and body.get('random_seed') is not None:
        random_seed = body.get('random_seed')

    system = build_system_context(
        start_time=start_time,
        end_time=end_time,
        job_id=job_id,
        data_source=ds,
        threshold=predict.get('threshold'),
        model_id=predict.get('model_id'),
        model_name=model_name or predict.get('model_name'),
        run_id=run_id,
        stage=stage,
    )

    global_env = normalize_env_dict(body.get('env') or body.get('variables'))
    stage_env = {}
    if stage:
        stage_env = normalize_env_dict(
            body.get(f'{stage}_env')
            or body.get('stage_env', {}).get(stage)
        )
    merged = merge_context(system, global_env, stage_env)

    # 兼容旧请求：顶层 sample_size / random_seed 写入 env（策略参数优先）
    if sample_size is not None and 'SAMPLE_SIZE' not in merged:
        try:
            n = int(sample_size)
            merged['SAMPLE_SIZE'] = str(n if n > 0 else 300)
        except (TypeError, ValueError):
            merged['SAMPLE_SIZE'] = '300'
    if random_seed is not None and 'RANDOM_SEED' not in merged:
        try:
            merged['RANDOM_SEED'] = str(int(random_seed))
        except (TypeError, ValueError):
            merged['RANDOM_SEED'] = '42'
    return merged
