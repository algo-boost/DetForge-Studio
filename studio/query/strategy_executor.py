"""策略执行：SQL 变量替换 + Python 筛选 + 可选建 query task。"""
from __future__ import annotations

import re

from studio.flow.flow_compiler import normalize_strategy, resolve_strategy_python
from studio.query.env_context import substitute_template
from studio.query.strategy_loader import get_all_strategies, get_all_templates


def substitute_sql_vars(sql, context=None):
    """替换 ${VAR} 占位符（兼容旧名）。"""
    return substitute_template(sql, context)


def ensure_predict_job_scope(sql, job_id):
    """predict_result 查询若未限定 job_id，自动追加 WHERE。"""
    if job_id is None or not sql:
        return sql
    if 'predict_result' not in sql.lower():
        return sql
    jid = int(job_id)
    lowered = sql.lower()
    if '${JOB_ID}' in sql or '${job_id}' in sql.lower() or f'job_id = {jid}' in lowered or f'job_id={jid}' in lowered.replace(' ', ''):
        return sql
    clause = f'job_id = {jid}'
    order = re.search(r'\border\s+by\b', sql, re.I)
    head = sql[:order.start()].rstrip() if order else sql.rstrip()
    tail = sql[order.start():] if order else ''
    if re.search(r'\bwhere\b', head, re.I):
        merged = f'{head} AND {clause}'
    else:
        merged = f'{head} WHERE {clause}'
    if tail:
        return f'{merged} {tail}'
    return merged


def infer_data_source(strategy, context=None, explicit=None):
    if explicit:
        return explicit
    ctx = context or {}
    if ctx.get('JOB_ID') or ctx.get('DATA_SOURCE') == 'predict_result':
        return 'predict_result'
    sql = (strategy or {}).get('sql_template') or ''
    if 'predict_result' in sql.lower():
        return 'predict_result'
    return 'detail'


def execute_filter_strategy(
    strategy,
    *,
    context=None,
    templates=None,
    sample_size=None,
    random_seed=None,
    data_source=None,
    build_task=True,
    strategy_id=None,
    strategy_name=None,
):
    """
    执行策略筛选。

    build_task=False 时仅返回统计（preview）；True 时调用 build_query_task。
    """
    from server.core import (
        build_query_task,
        execute_python_filter,
        get_db_client,
        parse_random_seed,
        sample_size_from_env,
    )

    context = dict(context or {})
    templates = templates if templates is not None else get_all_templates()
    strategy = normalize_strategy(dict(strategy), templates)

    sql_template = strategy.get('sql_template', '')
    if not sql_template:
        raise ValueError('策略无 SQL 模板')

    ds = infer_data_source(strategy, context, data_source)
    job_id = context.get('JOB_ID')
    sql = substitute_sql_vars(sql_template, context)
    if ds == 'predict_result':
        sql = ensure_predict_job_scope(sql, job_id)

    client = get_db_client()
    df = client.query(sql)
    if df is None:
        raise RuntimeError('数据库查询失败')
    if df.empty:
        return {
            'count': 0,
            'data': [],
            'task_id': None,
            'data_source': ds,
            'query_sql_executed': sql,
        }

    input_rows, input_cols = len(df), len(df.columns)
    python_code = ''
    console_output = ''
    execution_time = 0.0
    exec_mode = 'strategy'
    python_code, exec_mode = resolve_strategy_python(strategy, templates)
    if python_code:
        python_code = substitute_template(python_code, context)
        df, console_output, execution_time = execute_python_filter(
            df,
            python_code,
            capture_output=True,
            env_context=context,
            strategy=strategy,
        )
    if df.empty:
        return {
            'count': 0,
            'data': [],
            'task_id': None,
            'data_source': ds,
            'query_sql_executed': sql,
            'console_output': console_output or None,
            'execution_time': execution_time or None,
            'input_rows': input_rows,
            'input_cols': input_cols,
        }

    rows_before_sample = len(df)
    ctx_sample = sample_size_from_env(context)
    if ctx_sample is None and sample_size is not None:
        try:
            n = int(sample_size)
            ctx_sample = n if n > 0 else None
        except (TypeError, ValueError):
            ctx_sample = None
    eff_sample = ctx_sample
    eff_seed = parse_random_seed(
        (context or {}).get('RANDOM_SEED') if random_seed is None else random_seed
    )
    # 随机采样仅在 process_data 内（策略流 random_sample + SAMPLE_SIZE），不再二次采样
    post_sample_skipped = True

    sid = strategy_id or strategy.get('id') or ''
    sname = strategy_name or strategy.get('name') or ''

    query_meta = {
        'query_sql': sql_template,
        'query_sql_executed': sql,
        'python_code': python_code if python_code else strategy.get('python_code', ''),
        'flow': strategy.get('flow'),
        'filter_mode': strategy.get('filter_mode', ''),
        'start_time': context.get('START_TIME', ''),
        'end_time': context.get('END_TIME', ''),
        'strategy_id': sid,
        'strategy_name': sname,
        'sample_size': eff_sample,
        'random_seed': eff_seed,
        'rows_before_sample': rows_before_sample,
        'post_sample_skipped': post_sample_skipped,
        'query_mode': exec_mode if python_code else 'strategy',
        'data_source': ds,
        'env': dict(context),
    }
    if ds == 'predict_result':
        query_meta['predict_job_id'] = int(job_id) if job_id is not None else None
        if 'model_name' in df.columns and not df['model_name'].dropna().empty:
            query_meta['model_name'] = str(df['model_name'].dropna().iloc[0])
        if job_id is None and 'job_id' in df.columns and not df['job_id'].dropna().empty:
            try:
                query_meta['predict_job_id'] = int(df['job_id'].dropna().iloc[0])
            except (TypeError, ValueError):
                pass

    if not build_task:
        return {
            'count': len(df),
            'data_source': ds,
            'query_sql_executed': sql,
            'rows_before_sample': rows_before_sample,
            'sample_size': eff_sample,
            'post_sample_skipped': post_sample_skipped,
            'console_output': console_output or None,
            'execution_time': execution_time or None,
            'input_rows': input_rows,
            'input_cols': input_cols,
        }

    result_data, task_id = build_query_task(df, query_meta)
    return {
        'count': len(result_data),
        'data': result_data,
        'task_id': task_id,
        'data_source': ds,
        'query_sql_executed': sql,
        'sample_size': eff_sample,
        'random_seed': eff_seed,
        'rows_before_sample': rows_before_sample,
        'post_sample_skipped': post_sample_skipped,
        'console_output': console_output or None,
        'execution_time': execution_time or None,
        'input_rows': input_rows,
        'input_cols': input_cols,
        'filter_mode': strategy.get('filter_mode', ''),
    }


def execute_strategy_ref(
    stage_spec,
    *,
    context=None,
    strategies=None,
    templates=None,
    sample_size=None,
    random_seed=None,
    data_source=None,
    build_task=True,
):
    """按 stage 引用（strategy_id / snapshot）执行。"""
    from studio.query.strategy_loader import resolve_strategy_ref

    strategies = strategies if strategies is not None else get_all_strategies()
    strategy = resolve_strategy_ref(stage_spec, strategies)
    if strategy is None:
        return None
    sid = (stage_spec or {}).get('strategy_id') or strategy.get('id')
    overrides = (stage_spec or {}).get('overrides') or {}
    return execute_filter_strategy(
        strategy,
        context=context,
        templates=templates,
        sample_size=sample_size if sample_size is not None else overrides.get('sample_size'),
        random_seed=random_seed if random_seed is not None else overrides.get('random_seed'),
        data_source=data_source or overrides.get('data_source'),
        build_task=build_task,
        strategy_id=sid,
        strategy_name=strategy.get('name'),
    )
