"""历史回跑三阶段编排：Stage1 策略 → 预测 → Stage2 策略 → 筛选批次。"""
from __future__ import annotations

import copy
import json
import threading
import time
from datetime import datetime, timedelta

from studio.timezone_util import format_datetime, now_local
from studio.curation import curation_service
from studio.curation.dispositions import INTENT_REPLAY_EVAL
from studio.curation.replay_eval_service import _apply_replay_dispositions
from studio.forge import forge_db
from studio.query.strategy_executor import execute_strategy_ref
from studio.query.strategy_loader import get_all_strategies, get_all_templates, resolve_strategy_ref
from studio.query.env_context import build_stage_context, describe_strategy_variables


def resolve_time_window(spec=None):
    """解析时间窗 → (start_time, end_time) 字符串。"""
    spec = spec or {}
    if spec.get('start_time') and spec.get('end_time'):
        return str(spec['start_time']), str(spec['end_time'])
    preset = str(spec.get('preset') or spec.get('mode') or 'yesterday').strip().lower()
    now = now_local()
    fmt = '%Y-%m-%d %H:%M:%S'
    if preset in ('today', '当日'):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return format_datetime(start, fmt), format_datetime(now, fmt)
    if preset in ('yesterday', '昨日'):
        y = now.date() - timedelta(days=1)
        start = datetime.combine(y, datetime.min.time(), tzinfo=now.tzinfo)
        end = datetime.combine(y, datetime.max.time().replace(microsecond=0), tzinfo=now.tzinfo)
        return format_datetime(start, fmt), format_datetime(end, fmt)
    if preset in ('last_7d', '7d', '近7天'):
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        return format_datetime(start, fmt), format_datetime(now, fmt)
    raise ValueError(f'未知时间 preset: {preset}')


def _build_context(body, *, job_id=None, stage=None, run_id=None):
    body = body or {}
    stage_env = {}
    if stage == 'stage1':
        stage_env = (body.get('stage1_env') or {})
    elif stage == 'stage2':
        stage_env = (body.get('stage2_env') or {})
    start = str(stage_env.get('START_TIME') or '').strip()
    end = str(stage_env.get('END_TIME') or '').strip()
    if not start or not end:
        tw_start, tw_end = resolve_time_window(body.get('time_window') or {})
        if not start:
            start = tw_start
        if not end:
            end = tw_end
    return build_stage_context(
        body,
        stage=stage,
        job_id=job_id,
        run_id=run_id,
        start_time=start or None,
        end_time=end or None,
        time_preset='yesterday',
    )


def describe_workflow_variables(body=None):
    """返回回跑工作流各阶段可配置环境变量。"""
    body = body or {}
    strategies = get_all_strategies()
    out = {'stages': {}, 'global_env': body.get('env') or {}}

    for stage_key, stage_field in (('stage1', 'stage1'), ('stage2', 'stage2')):
        spec = body.get(stage_field)
        if not spec or spec.get('skip'):
            continue
        try:
            strategy = resolve_strategy_ref(spec, strategies)
        except ValueError:
            continue
        if strategy:
            out['stages'][stage_key] = describe_strategy_variables(strategy)

    predict = body.get('predict') or {}
    out['system_preview'] = build_stage_context(body, stage='preview')
    if predict.get('threshold') is not None:
        out['system_preview']['THRESHOLD'] = str(predict['threshold'])
    return out


def _snapshot_stage(stage_spec, strategies):
    if not stage_spec or stage_spec.get('skip'):
        return {'skip': True}
    if stage_spec.get('snapshot'):
        return {'snapshot': copy.deepcopy(stage_spec['snapshot'])}
    sid = stage_spec.get('strategy_id')
    if not sid:
        return {}
    strat = resolve_strategy_ref(stage_spec, strategies)
    return {
        'strategy_id': sid,
        'snapshot': copy.deepcopy(strat),
        'overrides': copy.deepcopy(stage_spec.get('overrides') or {}),
    }


def _normalize_spec(body):
    """持久化 spec：含策略 snapshot 便于复现。"""
    strategies = get_all_strategies()
    spec = copy.deepcopy(body or {})
    for key in ('stage1', 'stage2'):
        if spec.get(key):
            spec[key] = _snapshot_stage(spec[key], strategies)
    stage1_env = spec.get('stage1_env') or {}
    tw = dict(spec.get('time_window') or {})
    if stage1_env.get('START_TIME'):
        tw['start_time'] = stage1_env['START_TIME']
    if stage1_env.get('END_TIME'):
        tw['end_time'] = stage1_env['END_TIME']
    if not (tw.get('start_time') and tw.get('end_time')):
        start, end = resolve_time_window(tw)
        tw['start_time'] = start
        tw['end_time'] = end
    spec['time_window'] = tw
    return spec


def _stage_spec_from_persisted(stage):
    if not stage or stage.get('skip'):
        return {'skip': True}
    if stage.get('snapshot') and not stage.get('strategy_id'):
        return {'snapshot': stage['snapshot'], 'overrides': stage.get('overrides') or {}}
    return {
        'strategy_id': stage.get('strategy_id'),
        'snapshot': stage.get('snapshot'),
        'overrides': stage.get('overrides') or {},
    }


def preview(body=None):
    """预览 stage1 / stage2 匹配行数（不建 task）。"""
    body = body or {}
    strategies = get_all_strategies()
    templates = get_all_templates()
    out = {'stages': {}}

    existing_job = body.get('existing_predict_job_id') or body.get('predict_job_id')
    skip_stage1 = bool(body.get('skip_stage1') or body.get('stage1', {}).get('skip') or existing_job)

    if not skip_stage1 and body.get('stage1'):
        ctx = _build_context(body, stage='stage1')
        r1 = execute_strategy_ref(
            body['stage1'],
            context=ctx,
            strategies=strategies,
            templates=templates,
            data_source='detail',
            build_task=False,
        )
        out['stages']['stage1'] = {
            'count': r1.get('count', 0) if r1 else 0,
            'data_source': 'detail',
            'time_window': {'start_time': ctx['START_TIME'], 'end_time': ctx['END_TIME']},
        }

    stage2_spec = body.get('stage2')
    job_for_stage2 = existing_job
    if stage2_spec and job_for_stage2:
        ctx2 = _build_context(body, job_id=job_for_stage2, stage='stage2')
        r2 = execute_strategy_ref(
            stage2_spec,
            context=ctx2,
            strategies=strategies,
            templates=templates,
            data_source='predict_result',
            build_task=False,
        )
        out['stages']['stage2'] = {
            'count': r2.get('count', 0) if r2 else 0,
            'predict_job_id': int(job_for_stage2),
            'data_source': 'predict_result',
        }
    elif stage2_spec and not skip_stage1:
        out['stages']['stage2'] = {
            'count': None,
            'note': '需完成预测后预览 Stage2',
        }

    return out


def wait_for_predict_job(job_id, timeout=7200, poll=5):
    deadline = time.time() + float(timeout)
    while time.time() < deadline:
        job = forge_db.get_job(job_id)
        if not job:
            raise ValueError(f'预测作业不存在: {job_id}')
        st = job.get('status')
        if st == 'done':
            return job
        if st in ('failed', 'cancelled', 'canceled'):
            raise RuntimeError(job.get('error') or f'预测作业状态: {st}')
        time.sleep(float(poll))
    raise TimeoutError(f'等待预测作业 #{job_id} 超时 ({timeout}s)')


def _enqueue_predict(task_id, predict_spec, run_label='replay'):
    from studio.forge import forge_service

    predict_spec = predict_spec or {}
    image_source = {'type': 'task', 'task_id': str(task_id)}
    if predict_spec.get('selected_indices'):
        image_source['selected_indices'] = predict_spec['selected_indices']
    name = predict_spec.get('name') or f'{run_label}-predict'
    threshold = predict_spec.get('threshold')

    if predict_spec.get('train_id'):
        return forge_service.enqueue_platform_predict_job(
            train_id=int(predict_spec['train_id']),
            model_name=predict_spec.get('model_name'),
            image_source=image_source,
            name=name,
            threshold=threshold if threshold is not None else 0.1,
        )
    model_id = predict_spec.get('model_id')
    if not model_id:
        raise ValueError('predict 需要 model_id 或 train_id')
    return forge_service.enqueue_predict_job(
        model_id=int(model_id),
        image_source=image_source,
        name=name,
        threshold=threshold,
        device=predict_spec.get('device'),
        intra_concurrency=int(predict_spec.get('intra_concurrency') or 1),
    )


def _run_pipeline(run_id):
    from flask import current_app

    run = forge_db.get_replay_run(run_id)
    if not run:
        return
    spec = run.get('spec_json') or {}
    strategies = get_all_strategies()
    templates = get_all_templates()
    result = {'run_id': run_id}

    try:
        forge_db.update_replay_run(run_id, status='running', stage='stage1', error=None)
        stage1_spec = _stage_spec_from_persisted(spec.get('stage1') or {})
        stage2_spec = _stage_spec_from_persisted(spec.get('stage2') or {})
        existing_job = spec.get('existing_predict_job_id') or spec.get('predict_job_id')
        skip_stage1 = bool(
            spec.get('skip_stage1')
            or stage1_spec.get('skip')
            or existing_job
            or spec.get('stage1_task_id')
        )

        stage1_task_id = spec.get('stage1_task_id')
        predict_job_id = int(existing_job) if existing_job else None

        if not skip_stage1:
            if not stage1_spec or stage1_spec.get('skip'):
                raise ValueError('未跳过 Stage1 时必须配置 stage1 策略')
            ctx1 = _build_context(spec, stage='stage1', run_id=run_id)
            r1 = execute_strategy_ref(
                stage1_spec,
                context=ctx1,
                strategies=strategies,
                templates=templates,
                data_source='detail',
                build_task=True,
            )
            if not r1 or not r1.get('task_id'):
                raise ValueError('Stage1 筛选无结果')
            stage1_task_id = r1['task_id']
            result['stage1'] = {'task_id': stage1_task_id, 'count': r1.get('count', 0)}
            forge_db.update_replay_run(run_id, stage1_task_id=stage1_task_id, stage='predict')

            predict_spec = spec.get('predict') or {}
            if not predict_job_id:
                pred = _enqueue_predict(stage1_task_id, predict_spec, run_label=f'replay-{run_id}')
                predict_job_id = int(pred['job_id'])
                result['predict'] = {'job_id': predict_job_id, 'total': pred.get('total')}
                forge_db.update_replay_run(run_id, predict_job_id=predict_job_id)
        elif not predict_job_id:
            raise ValueError('跳过 Stage1 时需要 existing_predict_job_id 或 stage1_task_id + predict')

        if not predict_job_id and stage1_task_id:
            predict_spec = spec.get('predict') or {}
            pred = _enqueue_predict(stage1_task_id, predict_spec, run_label=f'replay-{run_id}')
            predict_job_id = int(pred['job_id'])
            result['predict'] = {'job_id': predict_job_id, 'total': pred.get('total')}
            forge_db.update_replay_run(run_id, predict_job_id=predict_job_id, stage='predict')

        if predict_job_id:
            forge_db.update_replay_run(run_id, stage='predict_wait')
            job = wait_for_predict_job(
                predict_job_id,
                timeout=spec.get('predict_timeout') or 7200,
                poll=spec.get('predict_poll') or 5,
            )
            result['predict'] = {
                'job_id': predict_job_id,
                'done': job.get('done'),
                'total': job.get('total'),
                'status': job.get('status'),
            }

        if not stage2_spec or stage2_spec.get('skip'):
            raise ValueError('Stage2 策略未配置')

        forge_db.update_replay_run(run_id, stage='stage2')
        ctx2 = _build_context(spec, job_id=predict_job_id, stage='stage2', run_id=run_id)
        r2 = execute_strategy_ref(
            stage2_spec,
            context=ctx2,
            strategies=strategies,
            templates=templates,
            data_source='predict_result',
            build_task=True,
        )
        if not r2 or not r2.get('task_id'):
            raise ValueError('Stage2 筛选无结果')
        stage2_task_id = r2['task_id']
        result['stage2'] = {'task_id': stage2_task_id, 'count': r2.get('count', 0)}
        forge_db.update_replay_run(run_id, stage2_task_id=stage2_task_id, stage='curation')

        sid = (stage2_spec.get('strategy_id') or (stage2_spec.get('snapshot') or {}).get('id') or f'replay_run_{run_id}')
        sname = (stage2_spec.get('snapshot') or {}).get('name') or f'历史回跑 #{run_id}'
        batch = curation_service.create_from_task(
            stage2_task_id,
            strategy_id=sid,
            strategy_name=sname,
            data_source='predict_result',
            intent_type=INTENT_REPLAY_EVAL,
            reviewer=spec.get('reviewer'),
            note=spec.get('note') or f'历史回跑 run #{run_id} predict_job #{predict_job_id}',
        )
        _apply_replay_dispositions(batch['id'], 'ng_only')
        result['curation'] = {'batch_id': batch['id'], 'batch_code': batch.get('batch_code')}
        forge_db.update_replay_run(
            run_id,
            status='done',
            stage='done',
            curation_batch_id=batch['id'],
            result_json=result,
        )
    except Exception as e:
        forge_db.update_replay_run(run_id, status='failed', error=str(e), result_json=result)
        raise


def start_run(body=None, app=None):
    """创建 replay_run 记录并后台执行。"""
    if not forge_db.schema_ready():
        raise RuntimeError('detforge 写库未初始化，请先建表')

    body = body or {}
    if not body.get('stage2'):
        raise ValueError('缺少 stage2 策略配置')

    spec = _normalize_spec(body)
    run_id = forge_db.create_replay_run(spec)

    if app is None:
        from flask import current_app
        app = current_app._get_current_object()

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(run_id, app),
        daemon=True,
        name=f'replay-run-{run_id}',
    )
    thread.start()
    return forge_db.get_replay_run(run_id)


def _run_pipeline_thread(run_id, app):
    with app.app_context():
        try:
            _run_pipeline(run_id)
        except Exception:
            pass


def get_run(run_id):
    run = forge_db.get_replay_run(run_id)
    if not run:
        raise ValueError('回跑任务不存在')
    return run
