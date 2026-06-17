"""工作流步骤处理器注册表。"""
from __future__ import annotations

import re
import time

from studio.curation.replay_run_service import resolve_time_window, wait_for_predict_job
from studio.forge import forge_db
from studio.query.strategy_executor import execute_strategy_ref
from studio.query.strategy_loader import get_all_strategies, get_all_templates


def _resolve_expr(expr, context):
    if expr.startswith('params.'):
        cur = context.get('params') or {}
        for part in expr.split('.')[1:]:
            if isinstance(cur, dict):
                cur = cur.get(part)
            else:
                return None
        return cur
    if expr.startswith('steps.'):
        rest = expr[len('steps.'):]
        steps_ctx = context.get('steps') or {}
        for step_id in sorted(steps_ctx.keys(), key=len, reverse=True):
            if rest == step_id:
                return steps_ctx.get(step_id)
            prefix = f'{step_id}.'
            if rest.startswith(prefix):
                cur = steps_ctx.get(step_id)
                for part in rest[len(prefix):].split('.'):
                    if isinstance(cur, dict):
                        cur = cur.get(part)
                    else:
                        return None
                return cur
        return None
    return None


def resolve_templates(value, context):
    """将 params 中的 {{params.x}} / {{steps.id.key}} 替换为实际值。"""
    if isinstance(value, str):
        stripped = value.strip()
        whole = re.fullmatch(r'\{\{([^}]+)\}\}', stripped)
        if whole:
            resolved = _resolve_expr(whole.group(1).strip(), context)
            if resolved is not None:
                return resolved

        def _repl(m):
            resolved = _resolve_expr(m.group(1).strip(), context)
            if resolved is None:
                return m.group(0)
            return str(resolved)

        return re.sub(r'\{\{([^}]+)\}\}', _repl, value)
    if isinstance(value, dict):
        return {k: resolve_templates(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(v, context) for v in value]
    return value


def _merge_env_overrides(ctx, env):
    """env 中非空值覆盖 ctx（策略环境变量最高优先级）。"""
    if not isinstance(env, dict):
        return ctx
    out = dict(ctx)
    for key, val in env.items():
        if val is None:
            continue
        text = str(val).strip()
        if not text:
            continue
        k = str(key).upper()
        if k in ('START_TIME', 'END_TIME'):
            out[k] = text
        else:
            out[key] = text
    return out


def _build_query_context(params, context=None):
    tw = params.get('time_window')
    if isinstance(tw, str):
        try:
            import json
            tw = json.loads(tw)
        except (TypeError, ValueError):
            tw = {'preset': tw}
    if not isinstance(tw, dict):
        tw = {}
    start, end = resolve_time_window(tw)
    ctx = {
        'START_TIME': start,
        'END_TIME': end,
    }
    step_env = params.get('env') or {}
    if isinstance(step_env, dict):
        ctx = _merge_env_overrides(ctx, step_env)
    global_env = (context or {}).get('resolved_env')
    if global_env is None:
        run_params = (context or {}).get('params') or {}
        from studio.forge.run_env_resolver import resolve_run_params_env
        global_env = resolve_run_params_env(
            run_params,
            ctx={
                **(context or {}),
                'run_id': (context or {}).get('run_id'),
            },
        )
    if isinstance(global_env, dict):
        ctx = _merge_env_overrides(ctx, global_env)
    return ctx


def _strategy_spec(strategy_id):
    return {'strategy_id': str(strategy_id)}


def run_query_step(params, context):
    """执行查询步骤：按 strategy_id 落 task，空结果标记 skipped。

    直接调用 execute_strategy_ref（查询执行的唯一真源），不再回到
    tools.query.service.dispatch —— 后者 action=execute 会再调本函数，
    形成无限递归（maximum recursion depth exceeded）。
    """
    strategy_id = params.get('strategy_id')
    if not strategy_id and not params.get('strategy_snapshot'):
        return {'skipped': True, 'reason': 'no_strategy_id'}

    qctx = _build_query_context(params, context)
    ds = params.get('data_source') or 'detail'
    jid = params.get('predict_job_id') or params.get('job_id')
    if jid:
        qctx['JOB_ID'] = str(int(jid))
        qctx['PREDICT_JOB_ID'] = str(int(jid))
        ds = 'predict_result'

    stage_spec = {'strategy_id': str(strategy_id)}
    if params.get('strategy_snapshot'):
        stage_spec = {'snapshot': params['strategy_snapshot']}

    result = execute_strategy_ref(
        stage_spec,
        context=qctx,
        sample_size=params.get('sample_size'),
        random_seed=params.get('random_seed'),
        data_source=ds,
        build_task=True,
    )
    if result is None:
        raise ValueError(f'策略不存在: {strategy_id}')

    count = int(result.get('count') or 0)
    task_id = result.get('task_id')
    if not task_id or count == 0:
        return {'skipped': True, 'reason': 'empty_result', 'count': count, 'row_count': count}
    return {
        'action': 'execute',
        'strategy_id': strategy_id,
        'task_id': task_id,
        'count': count,
        'row_count': count,
        'data_source': result.get('data_source') or ds,
    }


def run_predict_step(params, context):
    task_id = params.get('task_id')
    if not task_id:
        return {'skipped': True, 'reason': 'no_task_id'}
    from studio.curation.replay_run_service import _enqueue_predict

    predict_spec = {
        'model_id': params.get('model_id'),
        'train_id': params.get('train_id'),
        'model_name': params.get('model_name'),
        'threshold': params.get('threshold'),
        'device': params.get('device'),
        'intra_concurrency': params.get('intra_concurrency'),
        'name': params.get('name') or f"workflow-predict-{context.get('run_id')}",
    }
    if not predict_spec.get('model_id') and not predict_spec.get('train_id'):
        raise ValueError('predict 步骤需要 model_id 或 train_id')
    pred = _enqueue_predict(task_id, predict_spec, run_label=f"wf-{context.get('run_id')}")
    job_id = int(pred['job_id'])
    timeout = float(params.get('timeout') or 7200)
    poll = float(params.get('poll') or 5)
    job = wait_for_predict_job(job_id, timeout=timeout, poll=poll)
    return {
        'job_id': job_id,
        'total': job.get('total'),
        'done': job.get('done'),
        'status': job.get('status'),
    }


def run_curation_create_step(params, context):
    from studio.curation import curation_service
    from studio.curation.replay_eval_service import _apply_replay_dispositions

    task_id = params.get('task_id')
    if not task_id:
        return {'skipped': True, 'reason': 'no_task_id'}
    batch = curation_service.create_from_task(
        task_id,
        strategy_id=params.get('strategy_id'),
        strategy_name=params.get('strategy_name'),
        reviewer=params.get('reviewer'),
        note=params.get('note'),
        data_source=params.get('data_source'),
        intent_type=params.get('intent_type'),
    )
    if (params.get('intent_type') or batch.get('intent_type')) == 'replay_eval':
        mode = params.get('replay_disposition_mode') or 'ng_only'
        _apply_replay_dispositions(batch['id'], mode)
        batch = forge_db.get_curation_batch(batch['id'])
    return {
        'batch_id': batch['id'],
        'batch_code': batch.get('batch_code'),
    }


def run_curation_export_step(params, context):
    from studio.curation import curation_service

    batch_id = int(params.get('batch_id'))
    result = curation_service.export_batch(
        batch_id, include_images=params.get('include_images', True),
    )
    return {
        'batch_id': batch_id,
        'export_dir': result.get('out_dir'),
        'items': result.get('items'),
        'images_copied': result.get('images_copied'),
    }


def run_gate_human_step(params, context):
    batch_id = params.get('batch_id')
    if batch_id:
        batch_id = int(batch_id)
    return {
        'gate_type': params.get('gate_type') or 'curation_coco_edit',
        'batch_id': batch_id,
        'instructions': params.get('instructions') or '请上传筛选后的 COCO JSON',
        'waiting': True,
    }


def run_curation_import_step(params, context):
    batch_id = int(params.get('batch_id'))
    batch = forge_db.get_curation_batch(batch_id)
    if not batch:
        raise ValueError(f'批次不存在: {batch_id}')
    st = batch.get('status')
    if st in ('imported', 'archived', 'handoff_ready', 'handoff_done', 'closed'):
        return {
            'batch_id': batch_id,
            'status': st,
            'already_imported': True,
            'keep_count': batch.get('keep_count'),
            'reject_count': batch.get('reject_count'),
        }
    raise ValueError('尚未上传筛选 COCO，请先在筛选归档页上传或确认已导入')


def run_curation_archive_step(params, context):
    from studio.curation import curation_service

    batch_id = int(params.get('batch_id'))
    result = curation_service.archive_batch(
        batch_id,
        archive_dir=params.get('archive_dir'),
        copy_images=params.get('copy_images', True),
        treat_pending_as=params.get('treat_pending_as', 'reject'),
    )
    return {
        'batch_id': batch_id,
        'archive_dir': result.get('archive_dir'),
        'keep_count': result.get('keep_count'),
    }


def run_notify_step(params, context):
    from studio.forge.workflow_notify import emit_event

    event = params.get('event') or 'workflow_done'
    run = forge_db.get_workflow_run(context.get('run_id'))
    schedule = None
    if run and run.get('schedule_id'):
        schedule = forge_db.get_workflow_schedule(run['schedule_id'])
    emit_event(event, run=run, schedule=schedule, extra=params.get('extra'))
    return {'event': event}


_STEP_HANDLERS_LEGACY = {
    'query': run_query_step,
    'predict': run_predict_step,
    'curation_create': run_curation_create_step,
    'curation_export': run_curation_export_step,
    'gate_human': run_gate_human_step,
    'curation_import': run_curation_import_step,
    'curation_archive': run_curation_archive_step,
    'notify': run_notify_step,
}


def _handler_for_kind(kind: str):
    from capabilities.step_bridge import execute_via_registry, use_registry
    if use_registry():
        return lambda params, context: execute_via_registry(kind, params, context)
    fn = _STEP_HANDLERS_LEGACY.get(kind)
    if not fn:
        return None
    return fn


class _StepHandlersProxy(dict):
    """兼容 dict 接口；IISP_USE_REGISTRY=1 时走 Capability Registry。"""

    def get(self, key, default=None):
        h = _handler_for_kind(key)
        return h if h is not None else default

    def __contains__(self, key):
        if key in _STEP_HANDLERS_LEGACY:
            return True
        from capabilities.registry import get_registry
        return get_registry().get(key) is not None


STEP_HANDLERS = _StepHandlersProxy()
