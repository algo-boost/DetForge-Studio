"""组合编排运行级 env：模板/脚本推导与 legacy 兼容。"""
from __future__ import annotations

from datetime import datetime, timedelta

from studio.curation.replay_run_service import resolve_time_window
from studio.forge.run_env_templates import RUN_ENV_TEMPLATES, get_run_env_template
from studio.timezone_util import format_datetime, now_local


def _merge_env_dict(base, overrides):
    out = {str(k).upper() if str(k).upper() in ('START_TIME', 'END_TIME') else str(k): str(v).strip()
           for k, v in (base or {}).items()
           if v is not None and str(v).strip()}
    for k, v in (overrides or {}).items():
        if v is None:
            continue
        text = str(v).strip()
        if not text:
            continue
        key = str(k).upper() if str(k).upper() in ('START_TIME', 'END_TIME') else str(k)
        out[key] = text
    return out


def default_inputs_for_template(template_id):
    tpl = get_run_env_template(template_id)
    if not tpl:
        return {}
    out = {}
    for row in tpl.get('param_schema') or []:
        key = str(row.get('key') or '').strip()
        if not key:
            continue
        if row.get('default') is not None:
            out[key] = row['default']
    return out


def normalize_env_spec(raw=None):
    """规范化 env_spec；legacy time_window 迁移为 time_preset 模板。"""
    spec = dict(raw or {})
    kind = str(spec.get('kind') or 'template').strip().lower()
    if kind == 'manual':
        return {'kind': 'manual'}
    if kind == 'script':
        return {
            'kind': 'script',
            'script': str(spec.get('script') or spec.get('script_override') or ''),
            'inputs': dict(spec.get('inputs') or {}),
        }
    tid = str(spec.get('template_id') or 'time_preset')
    inputs = dict(spec.get('inputs') or {})
    defaults = default_inputs_for_template(tid)
    merged_inputs = {**defaults, **inputs}
    out = {
        'kind': 'template',
        'template_id': tid,
        'inputs': merged_inputs,
    }
    if spec.get('script_override'):
        out['script_override'] = str(spec['script_override'])
    return out


def normalize_run_params_defaults(raw=None):
    """规范化 run_params_defaults（含 legacy time_window + env KV）。"""
    data = dict(raw or {})
    if data.get('env_spec'):
        return {
            'env_spec': normalize_env_spec(data['env_spec']),
            'env': dict(data.get('env') or {}),
        }
    tw = data.get('time_window') or {}
    preset = tw.get('preset') if isinstance(tw, dict) else None
    if tw.get('start_time') and tw.get('end_time'):
        return {
            'env_spec': {
                'kind': 'template',
                'template_id': 'time_absolute',
                'inputs': {
                    'start_time': str(tw['start_time']),
                    'end_time': str(tw['end_time']),
                },
            },
            'env': dict(data.get('env') or {}),
        }
    return {
        'env_spec': {
            'kind': 'template',
            'template_id': 'time_preset',
            'inputs': {'preset': preset or 'yesterday'},
        },
        'env': dict(data.get('env') or {}),
    }


def eval_compute_env_script(script, inputs=None, *, ctx=None, now=None):
    src = str(script or '').strip()
    if not src:
        raise ValueError('env 推导脚本为空')
    now = now or now_local()
    ns = {
        'now': now,
        'now_local': now_local,
        'datetime': datetime,
        'timedelta': timedelta,
        'format_datetime': format_datetime,
        'resolve_time_window': resolve_time_window,
        'inputs': dict(inputs or {}),
        'ctx': dict(ctx or {}),
    }
    exec(src, ns)  # noqa: S102
    fn = ns.get('compute_env')
    if not callable(fn):
        raise ValueError('脚本须定义 compute_env(now, inputs, ctx) 函数')
    result = fn(now, dict(inputs or {}), dict(ctx or {}))
    if not isinstance(result, dict):
        raise ValueError('compute_env 须返回 dict')
    out = {}
    for k, v in result.items():
        if v is None:
            continue
        text = str(v).strip()
        if text:
            out[str(k).upper() if str(k).upper() in ('START_TIME', 'END_TIME') else str(k)] = text
    return out


def eval_env_spec(env_spec, *, ctx=None, now=None):
    spec = normalize_env_spec(env_spec)
    kind = spec.get('kind')
    if kind == 'manual':
        return {}
    inputs = spec.get('inputs') or {}
    script = spec.get('script_override') or spec.get('script')
    if kind == 'template':
        tpl = get_run_env_template(spec.get('template_id'))
        if not tpl:
            raise ValueError(f'未知 env 模板: {spec.get("template_id")}')
        script = script or tpl.get('script')
    if not script:
        raise ValueError('缺少 env 推导脚本')
    return eval_compute_env_script(script, inputs, ctx=ctx, now=now)


def enrich_run_params_for_engine(params):
    """为 workflow 步骤模板保留 time_window（query 步 {{params.time_window}}）。"""
    p = normalize_run_params_defaults(params)
    spec = p.get('env_spec') or {}
    if spec.get('kind') == 'template' and spec.get('template_id') == 'time_preset':
        preset = (spec.get('inputs') or {}).get('preset') or 'yesterday'
        p = dict(p)
        p['time_window'] = {'preset': preset}
    else:
        p = dict(p)
        if not p.get('time_window'):
            p['time_window'] = {'preset': 'yesterday'}
    return p


def resolve_run_params_env(params, *, ctx=None, now=None):
    """从 run params 推导最终全局 env（模板/脚本 + 静态 env 补充）。"""
    params = dict(params or {})
    ctx = dict(ctx or {})
    ctx.setdefault('params', params)

    derived = {}
    env_spec = params.get('env_spec')
    if env_spec:
        derived = eval_env_spec(env_spec, ctx=ctx, now=now)
    elif params.get('time_window'):
        start, end = resolve_time_window(params.get('time_window'))
        derived = {'START_TIME': start, 'END_TIME': end}

    static = params.get('env') or {}
    return _merge_env_dict(derived, static)


def preview_run_env(body, *, now=None):
    """预览 env 推导结果。"""
    params = normalize_run_params_defaults({
        'env_spec': body.get('env_spec'),
        'env': body.get('env') or {},
        'time_window': body.get('time_window'),
    })
    ctx = dict(body.get('ctx') or {})
    if body.get('flow_id'):
        ctx['flow_id'] = body['flow_id']
    env = resolve_run_params_env(params, ctx=ctx, now=now)
    return {'env': env, 'params': params}
