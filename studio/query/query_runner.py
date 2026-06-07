"""查询执行管线（同步 API 与后台 query job 共用）。"""
from __future__ import annotations

import traceback

from studio.query.env_context import (
    build_stage_context,
    find_unresolved_template_vars,
    format_unresolved_vars_error,
    substitute_template,
)
from studio.query.strategy_loader import get_all_strategies, get_all_templates


def _resolve_query_python_for_request(data, templates, resolve_query_python):
    """解析执行用 Python；请求体带 flow 时优先按 flow 编译规则（避免陈旧 filter_rules_code）。"""
    data = dict(data or {})
    flow = data.get('flow') or {}
    filter_mode = (data.get('filter_mode') or '').strip()
    if flow.get('nodes') and filter_mode in ('flow', 'split', 'rules', ''):
        from server.core import _compile_rules_from_flow

        flow_rules = _compile_rules_from_flow(flow, templates)
        if flow_rules:
            data['filter_rules_code'] = flow_rules
    return resolve_query_python(data, templates)


def resolve_filter_rules_for_request(data, templates, resolve_filter_rules_code):
    """仅解析 apply_filter_rules 代码；与执行查询时 flow 优先逻辑一致。"""
    data = dict(data or {})
    flow = data.get('flow') or {}
    filter_mode = (data.get('filter_mode') or '').strip()
    if flow.get('nodes') and filter_mode in ('flow', 'split', 'rules', ''):
        from server.core import _compile_rules_from_flow

        flow_rules = _compile_rules_from_flow(flow, templates)
        if flow_rules:
            return flow_rules
    return resolve_filter_rules_code(data, templates)


def run_query_request(data, *, get_db_client, execute_python_filter, build_query_task,
                      sample_size_from_env, parse_random_seed, resolve_query_python):
    """
    执行完整查询。返回 dict（含 success）；失败时可带 status_code（400/500）。
    成功且有条目时含 data、task_id；空结果仅含 count=0。
    """
    data = data or {}
    sql_template = data.get('sql', '')
    start_time = data.get('start_time', '')
    end_time = data.get('end_time', '')
    templates = get_all_templates()
    flow = data.get('flow')
    filter_mode = data.get('filter_mode', '')

    try:
        python_code = _resolve_query_python_for_request(data, templates, resolve_query_python)
    except ValueError as e:
        return {'success': False, 'error': str(e), 'status_code': 400}

    if not sql_template:
        return {'success': False, 'error': 'SQL 查询语句不能为空', 'status_code': 400}

    strategy = get_all_strategies().get((data.get('strategy_id') or '').strip()) if data.get('strategy_id') else None
    env_schema = data.get('env_schema')
    if strategy and not env_schema:
        from studio.query.strategy_env_schema import merge_strategy_env_schema
        env_schema = merge_strategy_env_schema(strategy, templates)

    env_ctx = build_stage_context(
        data,
        start_time=start_time,
        end_time=end_time,
        job_id=data.get('predict_job_id') or data.get('job_id'),
        env_schema=env_schema,
    )
    sample_size = sample_size_from_env(env_ctx)
    random_seed = parse_random_seed(env_ctx.get('RANDOM_SEED'))
    sql = substitute_template(sql_template, env_ctx)
    unresolved = find_unresolved_template_vars(sql)
    if unresolved:
        return {
            'success': False,
            'error': format_unresolved_vars_error(unresolved, env_schema),
            'unresolved_vars': unresolved,
            'status_code': 400,
        }

    client = get_db_client()
    df = client.query(sql)
    if df is None:
        detail = getattr(client, 'last_query_error', None) or ''
        msg = f'查询失败：{detail}' if detail else '查询失败，请检查 SQL 语句和数据库连接'
        return {'success': False, 'error': msg, 'status_code': 500}

    if df.empty:
        return {'success': True, 'data': [], 'count': 0, 'message': '查询结果为空'}

    ds = data.get('data_source') or env_ctx.get('DATA_SOURCE') or 'detail'
    sql_had_ext = 'ext' in df.columns
    filter_warnings: list[str] = []
    if ds == 'predict_result':
        from studio.forge.predict_result_filters import hydrate_predict_result_df, predict_filter_warnings

        df = hydrate_predict_result_df(df)

    console_output = ''
    execution_time = 0.0
    input_rows, input_cols = len(df), len(df.columns)
    rows_before_sample = len(df)

    if python_code and python_code.strip():
        try:
            df, console_output, execution_time = execute_python_filter(
                df,
                python_code,
                capture_output=True,
                env_context=env_ctx,
                strategy=strategy,
            )
        except Exception as e:
            return {
                'success': False,
                'error': f'Python 筛选失败: {str(e)}',
                'traceback': traceback.format_exc(),
                'console_output': console_output,
                'status_code': 500,
            }

        if df.empty:
            resp = {'success': True, 'data': [], 'count': 0, 'message': '筛选后结果为空'}
            if console_output:
                resp['console_output'] = console_output
                resp['execution_time'] = execution_time
            return resp

    if ds == 'predict_result':
        from studio.forge.predict_result_filters import finalize_predict_result_df, predict_filter_warnings

        df = finalize_predict_result_df(df)
        filter_warnings = predict_filter_warnings(
            df,
            data_source=ds,
            sql_had_ext=sql_had_ext,
            python_ran=bool(python_code and python_code.strip()),
        )

    rows_before_sample = len(df)
    flow_payload = flow if flow and flow.get('nodes') else None
    post_sample_skipped = True

    query_meta = {
        'query_sql': sql_template,
        'query_sql_executed': sql,
        'python_code': python_code or '',
        'flow': flow_payload,
        'filter_mode': filter_mode or ('flow' if flow_payload else 'code'),
        'start_time': env_ctx.get('START_TIME', start_time),
        'end_time': env_ctx.get('END_TIME', end_time),
        'sample_size': sample_size,
        'random_seed': random_seed,
        'rows_before_sample': rows_before_sample,
        'post_sample_skipped': post_sample_skipped,
        'query_mode': 'free_query',
        'data_source': ds,
        'strategy_name': data.get('label') or data.get('strategy_name') or '',
    }
    if query_meta['data_source'] == 'predict_result':
        if 'model_name' in df.columns and not df['model_name'].dropna().empty:
            query_meta['model_name'] = str(df['model_name'].dropna().iloc[0])
        if 'job_id' in df.columns and not df['job_id'].dropna().empty:
            try:
                query_meta['job_id'] = int(df['job_id'].dropna().iloc[0])
            except (TypeError, ValueError):
                pass

    if python_code and python_code.strip():
        query_meta['console_output'] = console_output or ''
        query_meta['execution_time'] = execution_time
        query_meta['input_rows'] = input_rows
        query_meta['output_rows'] = rows_before_sample

    result_data, task_id = build_query_task(df, query_meta)

    resp = {
        'success': True,
        'data': result_data,
        'count': len(result_data),
        'task_id': task_id,
        'post_sample_skipped': post_sample_skipped,
        'sample_size': sample_size,
        'random_seed': random_seed,
        'rows_before_sample': rows_before_sample,
    }
    if python_code and python_code.strip():
        resp['console_output'] = console_output
        resp['execution_time'] = execution_time
        resp['input_rows'] = input_rows
        resp['input_cols'] = input_cols
        resp['output_rows'] = rows_before_sample
        resp['output_cols'] = len(df.columns)
    if filter_warnings:
        resp['filter_warnings'] = filter_warnings
    return resp
