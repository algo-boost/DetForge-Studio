"""查询策略 CRUD + 变量 + 校验。"""
from __future__ import annotations

import os

from studio.flow.flow_compiler import compile_filter_rules, extract_rules_compile_flow, normalize_strategy
from studio.flow.flow_schema import prepare_strategy, validate_flow
from studio.query.env_context import describe_strategy_variables
from studio.query.strategy_loader import (
    delete_strategy_by_id,
    effective_strategies_dir,
    get_all_strategies,
    get_all_templates,
)
from studio.timezone_util import format_iso_now


def _summarize(strategy: dict) -> dict:
    return {
        'id': strategy.get('id'),
        'name': strategy.get('name'),
        'category': strategy.get('category'),
        'data_source': strategy.get('data_source'),
        'description': strategy.get('description'),
    }


def strategy_list(params: dict) -> dict:
    templates = get_all_templates()
    strategies = get_all_strategies()
    full = str(params.get('full') or '').lower() in ('1', 'true', 'yes')
    if full:
        items = [normalize_strategy(dict(s), templates) for s in strategies.values()]
    else:
        items = [_summarize(normalize_strategy(dict(s), templates)) for s in strategies.values()]
    items.sort(key=lambda x: (x.get('category') or '', x.get('name') or x.get('id') or ''))
    return {'action': 'strategy.list', 'count': len(items), 'strategies': items, 'full': full}


def _load_strategy(strategy_id: str) -> dict:
    templates = get_all_templates()
    strategies = get_all_strategies()
    if strategy_id not in strategies:
        raise ValueError(f'策略不存在: {strategy_id}')
    return normalize_strategy(dict(strategies[strategy_id]), templates)


def strategy_get(params: dict) -> dict:
    sid = str(params.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('strategy.get 需要 strategy_id')
    return {'action': 'strategy.get', 'strategy_id': sid, 'strategy': _load_strategy(sid)}


def strategy_variables(params: dict) -> dict:
    sid = str(params.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('strategy.variables 需要 strategy_id')
    strategy = _load_strategy(sid)
    templates = get_all_templates()
    info = describe_strategy_variables(strategy, templates)
    from studio.query.preset_env import apply_env_schema_defaults
    from studio.query.python_preset_registry import active_presets_for_env_schema

    schema = info.get('custom_vars') or []
    info['python_presets'] = active_presets_for_env_schema(strategy)
    info['process_pipeline'] = strategy.get('process_pipeline') or []
    info['env_defaults'] = apply_env_schema_defaults({}, schema)
    return {'action': 'strategy.variables', 'strategy_id': sid, **info}


def strategy_validate(params: dict) -> dict:
    sid = str(params.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('strategy.validate 需要 strategy_id')
    strategy = _load_strategy(sid)
    flow = strategy.get('flow') or {}
    nodes = flow.get('nodes') if isinstance(flow, dict) else None
    if not nodes:
        return {
            'action': 'strategy.validate',
            'strategy_id': sid,
            'valid': True,
            'warnings': ['策略无 flow 节点，跳过 flow 校验'],
            'errors': [],
        }
    result = validate_flow(flow)
    return {
        'action': 'strategy.validate',
        'strategy_id': sid,
        'valid': len(result) == 0,
        'errors': result,
        'warnings': [],
    }


def strategy_save(params: dict) -> dict:
    data = dict(params.get('strategy') or params)
    sid = str(data.get('id') or params.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('strategy.save 需要 strategy.id')
    data['id'] = sid
    data['updated_at'] = format_iso_now()
    if 'created_at' not in data:
        data['created_at'] = data['updated_at']
    templates = get_all_templates()
    data = prepare_strategy(data)
    data = normalize_strategy(data, templates)
    if data.get('filter_mode') in ('flow', 'split', 'rules') and data.get('flow'):
        flow_errors = validate_flow(data['flow'])
        if flow_errors:
            raise ValueError('工作流校验失败: ' + '; '.join(flow_errors[:5]))
        rules_flow = extract_rules_compile_flow(data['flow'])
        compiled = compile_filter_rules(rules_flow, templates)
        if compiled['valid']:
            data['filter_rules_code'] = compiled['python_code']
    data.pop('is_preset', None)
    data.pop('_preset', None)
    strategies_dir = effective_strategies_dir()
    os.makedirs(strategies_dir, exist_ok=True)
    filepath = os.path.join(strategies_dir, f'{sid}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        import json
        json.dump(data, f, ensure_ascii=False, indent=2)
    return {'action': 'strategy.save', 'strategy_id': sid, 'path': filepath}


def strategy_delete(params: dict) -> dict:
    sid = str(params.get('strategy_id') or '').strip()
    if not sid:
        raise ValueError('strategy.delete 需要 strategy_id')
    ok, err = delete_strategy_by_id(sid)
    if not ok:
        raise ValueError(err or '删除失败')
    return {'action': 'strategy.delete', 'strategy_id': sid, 'deleted': True}


def strategy_execute(params: dict) -> dict:
    """策略执行引擎 — 对应 POST /api/strategies/execute。"""
    from tools.query.service._app import app_context

    data = dict(params or {})
    strategy_id = data.get('strategy_id', '')
    with app_context():
        from studio.query.env_context import build_stage_context
        from studio.query.strategy_executor import execute_strategy_ref

        env_ctx = build_stage_context(
            data,
            start_time=data.get('start_time', ''),
            end_time=data.get('end_time', ''),
            sample_size=data.get('sample_size'),
            random_seed=data.get('random_seed'),
        )
        if data.get('predict_job_id') or data.get('job_id'):
            jid = data.get('predict_job_id') or data.get('job_id')
            env_ctx['JOB_ID'] = str(int(jid))
            env_ctx['PREDICT_JOB_ID'] = str(int(jid))
            env_ctx['DATA_SOURCE'] = 'predict_result'

        stage_spec = {'strategy_id': strategy_id}
        if data.get('strategy_snapshot'):
            stage_spec = {'snapshot': data['strategy_snapshot']}

        result = execute_strategy_ref(
            stage_spec,
            context=env_ctx,
            sample_size=data.get('sample_size'),
            random_seed=data.get('random_seed'),
            data_source=data.get('data_source'),
            build_task=True,
        )
    if result is None:
        raise ValueError('策略不存在')
    return {'action': 'strategy.execute', 'strategy_id': strategy_id, **result}


def strategy_compile_pipeline(params: dict) -> dict:
    from studio.flow.process_pipeline import compile_process_pipeline

    pipeline = params.get('process_pipeline') or []
    templates = get_all_templates()
    result = compile_process_pipeline(pipeline, templates)
    return {'action': 'strategy.compile_pipeline', 'data': result}


def run_strategy_action(sub: str, params: dict) -> dict:
    if sub == 'list':
        return strategy_list(params)
    if sub == 'get':
        return strategy_get(params)
    if sub == 'variables':
        return strategy_variables(params)
    if sub == 'validate':
        return strategy_validate(params)
    if sub == 'save':
        return strategy_save(params)
    if sub == 'delete':
        return strategy_delete(params)
    if sub == 'execute':
        return strategy_execute(params)
    if sub == 'compile_pipeline' or sub == 'compile-pipeline':
        return strategy_compile_pipeline(params)
    raise ValueError(f'不支持的 strategy action: {sub}')
