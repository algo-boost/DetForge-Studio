"""组合编排流水线：稳定 flow_id / step_id、保存与 definition 编译。"""
from __future__ import annotations

import copy
import re
import time

from studio.forge import forge_db

COMPOSE_MODULES = {
    'query': {
        'kind': 'query',
        'defaults': {'data_source': 'detail'},
        'bind_rules': {},
    },
    'predict': {
        'kind': 'predict',
        'defaults': {},
        'bind_rules': {'task_id': {'from_kind': 'query', 'field': 'task_id'}},
    },
    'query_predict': {
        'kind': 'query',
        'defaults': {'data_source': 'predict_result'},
        'bind_rules': {'predict_job_id': {'from_kind': 'predict', 'field': 'job_id'}},
    },
    'curation_create': {
        'kind': 'curation_create',
        'defaults': {'data_source': 'predict_result', 'intent_type': 'replay_eval'},
        'bind_rules': {'task_id': {'from_kind': 'query', 'field': 'task_id'}},
    },
    'curation_export': {
        'kind': 'curation_export',
        'defaults': {'include_images': True},
        'bind_rules': {'batch_id': {'from_kind': 'curation_create', 'field': 'batch_id'}},
    },
    'gate_human': {
        'kind': 'gate_human',
        'defaults': {
            'gate_type': 'curation_coco_edit',
            'instructions': '请编辑出站 COCO 并上传后继续',
        },
        'bind_rules': {'batch_id': {'from_kind': 'curation_create', 'field': 'batch_id'}},
    },
    'curation_import': {
        'kind': 'curation_import',
        'defaults': {},
        'bind_rules': {'batch_id': {'from_kind': 'curation_create', 'field': 'batch_id'}},
    },
    'curation_archive': {
        'kind': 'curation_archive',
        'defaults': {'copy_images': True},
        'bind_rules': {'batch_id': {'from_kind': 'curation_create', 'field': 'batch_id'}},
    },
    'notify': {
        'kind': 'notify',
        'defaults': {'event': 'workflow_done'},
        'bind_rules': {},
    },
}

DEFAULT_MODULE_IDS = ['query', 'predict']

RUN_PARAMS_SCHEMA = {
    'env_spec': {
        'type': 'object',
        'label': '运行级 env 推导',
        'default': {
            'kind': 'template',
            'template_id': 'time_preset',
            'inputs': {'preset': 'yesterday'},
        },
    },
    'env': {
        'type': 'object',
        'label': '额外环境变量',
        'default': {},
    },
}


def normalize_flow_id(raw=None) -> str:
    slug = re.sub(r'[^a-z0-9_-]+', '_', str(raw or '').strip().lower()).strip('_')
    if not slug:
        slug = f'draft_{int(time.time())}'
    if not slug.startswith('flow_'):
        slug = f'flow_{slug}'
    return slug[:128]


def encode_step_id(flow_id: str, seq: int) -> str:
    return f'{normalize_flow_id(flow_id)}.s{int(seq):02d}'


def is_compose_flow_id(flow_id: str | None) -> bool:
    fid = str(flow_id or '')
    return fid.startswith('flow_') or fid.startswith('custom_')


def _strip_ui_params(params):
    if not isinstance(params, dict):
        return params
    return {k: v for k, v in params.items() if not str(k).startswith('_')}


def reindex_step_instances(flow_id, step_instances):
    fid = normalize_flow_id(flow_id)
    out = []
    for i, inst in enumerate(step_instances or []):
        row = dict(inst)
        module_id = row.get('module_id') or row.get('moduleId')
        row['uid'] = encode_step_id(fid, i + 1)
        row['module_id'] = module_id
        row.pop('moduleId', None)
        out.append(row)
    return out


def _find_upstream(built, from_kind):
    for item in reversed(built):
        if item['kind'] == from_kind:
            return item
    return None


def build_compose_definition(
    step_instances=None,
    *,
    flow_id='flow_draft',
    use_run_time_window=True,
):
    """将模块实例列表编译为 workflow_engine definition。"""
    fid = normalize_flow_id(flow_id)
    instances = reindex_step_instances(fid, step_instances)
    steps = []
    built = []

    for i, inst in enumerate(instances):
        module_id = inst.get('module_id') or inst.get('moduleId')
        meta = COMPOSE_MODULES.get(module_id)
        if not meta:
            continue

        step_id = inst.get('uid') or encode_step_id(fid, i + 1)
        params = _strip_ui_params({
            **(meta.get('defaults') or {}),
            **(inst.get('params') or {}),
        })

        if use_run_time_window and meta['kind'] == 'query':
            params['time_window'] = '{{params.time_window}}'

        for param, rule in (meta.get('bind_rules') or {}).items():
            upstream = _find_upstream(built, rule['from_kind'])
            if upstream:
                params[param] = f"{{{{steps.{upstream['id']}.{rule['field']}}}}}"

        step = {'id': step_id, 'kind': meta['kind'], 'params': params}
        if i > 0:
            step['requires'] = [steps[i - 1]['id']]
        steps.append(step)
        built.append({'id': step_id, 'kind': meta['kind'], 'module_id': module_id})

    return {
        'params_schema': copy.deepcopy(RUN_PARAMS_SCHEMA),
        'steps': steps,
    }


def build_linear_compose_definition(steps_config=None, *, flow_id='flow_draft'):
    steps_config = steps_config or {}
    instances = [
        {'module_id': 'query', 'params': steps_config.get('query') or {}},
        {'module_id': 'predict', 'params': steps_config.get('predict') or {}},
    ]
    return build_compose_definition(instances, flow_id=flow_id)


def default_step_instances(flow_id='flow_draft'):
    fid = normalize_flow_id(flow_id)
    return reindex_step_instances(
        fid,
        [{'module_id': mid, 'params': {}} for mid in DEFAULT_MODULE_IDS],
    )


def save_compose_flow(
    flow_id,
    *,
    name=None,
    description=None,
    step_instances,
    run_params_defaults=None,
):
    fid = normalize_flow_id(flow_id)
    indexed = reindex_step_instances(fid, step_instances)
    from studio.forge.run_env_resolver import normalize_run_params_defaults
    run_defaults = normalize_run_params_defaults(run_params_defaults)
    engine_def = build_compose_definition(indexed, flow_id=fid)
    definition = {
        **engine_def,
        'compose': {
            'version': 1,
            'flow_id': fid,
            'step_instances': indexed,
            'run_params_defaults': run_defaults,
        },
    }
    if run_defaults.get('env_spec'):
        definition['params_schema']['env_spec']['default'] = run_defaults['env_spec']
    if run_defaults.get('env'):
        definition['params_schema']['env']['default'] = run_defaults['env']

    forge_db.upsert_workflow_template({
        'id': fid,
        'name': name or fid,
        'description': description or '组合编排流水线',
        'definition': definition,
        'builtin': 0,
        'enabled': 1,
    })
    return get_compose_flow(fid)


def get_compose_flow(flow_id):
    tpl = forge_db.get_workflow_template(normalize_flow_id(flow_id))
    if not tpl:
        return None
    defn = tpl.get('definition') or {}
    compose = defn.get('compose') or {}
    if not compose.get('step_instances') and not defn.get('steps'):
        return None
    step_instances = compose.get('step_instances')
    if not step_instances and defn.get('steps'):
        step_instances = _step_instances_from_engine_steps(defn.get('steps') or [])
    from studio.forge.run_env_resolver import normalize_run_params_defaults
    return {
        'flow_id': tpl['id'],
        'name': tpl.get('name') or tpl['id'],
        'description': tpl.get('description'),
        'step_instances': step_instances or [],
        'run_params_defaults': normalize_run_params_defaults(compose.get('run_params_defaults')),
        'schedule': get_compose_schedule(tpl['id']),
        'definition': defn,
    }


def _step_instances_from_engine_steps(steps):
    """从已编译 steps 反推 module_id（只读模板兜底）。"""
    out = []
    kind_to_module = {
        meta['kind']: mid for mid, meta in COMPOSE_MODULES.items()
    }
    for step in steps:
        kind = step.get('kind')
        module_id = kind_to_module.get(kind, kind)
        for mid, meta in COMPOSE_MODULES.items():
            if meta['kind'] == kind and mid.startswith(kind.split('_')[0]):
                module_id = mid
                break
        out.append({
            'uid': step.get('id'),
            'module_id': module_id,
            'params': _strip_ui_params(step.get('params') or {}),
        })
    return out


def list_compose_flows():
    rows = []
    for tpl in forge_db.list_workflow_templates():
        fid = str(tpl.get('id') or '')
        defn = tpl.get('definition') or {}
        if defn.get('compose') or (is_compose_flow_id(fid) and defn.get('steps')):
            sched = forge_db.find_workflow_schedule_by_template(fid)
            rows.append({
                'flow_id': fid,
                'name': tpl.get('name') or fid,
                'description': tpl.get('description'),
                'step_count': len(defn.get('steps') or []),
                'updated': tpl.get('updated_at'),
                'schedule_enabled': bool(sched and sched.get('enabled')),
                'next_run_at': sched.get('next_run_at') if sched else None,
            })
    return rows


def get_compose_schedule(flow_id):
    fid = normalize_flow_id(flow_id)
    if not forge_db.get_workflow_template(fid):
        return None
    return forge_db.find_workflow_schedule_by_template(fid)


def upsert_compose_schedule(
    flow_id,
    *,
    cron_expr,
    name=None,
    params=None,
    enabled=1,
    mutex=1,
    timezone='Asia/Shanghai',
):
    from studio.forge.workflow_scheduler import compute_next_run

    from studio.forge.run_env_resolver import normalize_run_params_defaults

    fid = normalize_flow_id(flow_id)
    if not forge_db.get_workflow_template(fid):
        raise ValueError(f'流水线不存在: {fid}')
    if not cron_expr:
        raise ValueError('cron_expr 必填')

    existing = forge_db.find_workflow_schedule_by_template(fid)
    if params is None:
        if existing and existing.get('params'):
            params = existing['params']
        else:
            params = normalize_run_params_defaults({})
    else:
        params = normalize_run_params_defaults(params)

    nra = compute_next_run(cron_expr, timezone)
    payload = {
        'template_id': fid,
        'name': name or f'{fid} 定时',
        'cron_expr': str(cron_expr),
        'timezone': timezone,
        'params': params,
        'enabled': int(enabled),
        'mutex': int(mutex),
        'next_run_at': nra,
    }
    if existing:
        forge_db.update_workflow_schedule(existing['id'], **payload)
        return forge_db.get_workflow_schedule(existing['id'])
    sid = forge_db.create_workflow_schedule({**payload, 'next_run_at': nra})
    return forge_db.get_workflow_schedule(sid)


def save_compose_flow_with_schedule(
    flow_id,
    *,
    name=None,
    description=None,
    step_instances,
    run_params_defaults=None,
    schedule=None,
):
    """保存流水线并可选更新定时调度（一次提交）。"""
    flow = save_compose_flow(
        flow_id,
        name=name,
        description=description,
        step_instances=step_instances,
        run_params_defaults=run_params_defaults,
    )
    if not schedule:
        return {**flow, 'schedule': get_compose_schedule(flow['flow_id'])}
    run_defaults = run_params_defaults or flow.get('run_params_defaults') or {}
    sched = upsert_compose_schedule(
        flow['flow_id'],
        cron_expr=schedule.get('cron_expr'),
        name=schedule.get('name') or f"{flow.get('name') or flow['flow_id']} 定时",
        params=schedule.get('params') or run_defaults,
        enabled=schedule.get('enabled', 1),
        mutex=schedule.get('mutex', 1),
        timezone=schedule.get('timezone') or 'Asia/Shanghai',
    )
    return {**flow, 'schedule': sched}
