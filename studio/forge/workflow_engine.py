"""工作流编排引擎：DAG 调度、分支、人工卡点。"""
from __future__ import annotations

import logging
import threading
import traceback

from studio.forge import forge_db
from studio.forge.workflow_graph import (
    all_nodes_terminal,
    find_runnable_nodes,
    graph_for_template,
    has_waiting_human,
    normalize_definition,
    propagate_branch_skips,
)
from studio.forge.workflow_notify import emit_event
from studio.forge.workflow_steps import STEP_HANDLERS, resolve_templates
from studio.forge.workflow_templates import ensure_builtin_templates
from studio.timezone_util import format_now

logger = logging.getLogger('detforge.workflow.engine')

_active_threads: dict[int, threading.Thread] = {}
_thread_lock = threading.Lock()


def _now():
    return format_now()


def _get_schedule_for_run(run):
    if run and run.get('schedule_id'):
        return forge_db.get_workflow_schedule(run['schedule_id'])
    return None


def _merge_step_output(context, step_id, output):
    ctx = dict(context or {})
    steps = dict(ctx.get('steps') or {})
    steps[step_id] = output or {}
    ctx['steps'] = steps
    return ctx


def _node_def(graph, step_id):
    for n in graph.get('nodes') or []:
        if str(n['id']) == str(step_id):
            return n
    return None


def execute_step(run, node_def, step_run):
    """执行单个步骤，返回 (output, skipped_bool)。"""
    run_id = run['id']
    kind = node_def['kind']
    handler = STEP_HANDLERS.get(kind)
    if not handler:
        raise ValueError(f'未知步骤类型: {kind}')

    context = dict(run.get('context') or {})
    context['run_id'] = run_id
    resolved = resolve_templates(node_def.get('params') or {}, context)

    if kind in ('gate_human', 'notify'):
        output = handler(resolved, context)
        if isinstance(output, dict) and output.get('skipped'):
            return output, True
        return output, False

    output = handler(resolved, context)
    if isinstance(output, dict) and output.get('skipped'):
        return output, True
    return output, False


def _propagate_skips(run_id, graph):
    step_runs = forge_db.list_workflow_step_runs(run_id)
    propagate_branch_skips(
        run_id, graph, step_runs,
        update_fn=forge_db.update_workflow_step_run,
        now_fn=_now,
    )


def advance_run(run_id, *, max_steps=20):
    """DAG 推进：可运行节点调度 + 分支传播。"""
    steps_done = 0
    while steps_done < max_steps:
        run = forge_db.get_workflow_run(run_id)
        if not run:
            return
        if run['status'] in ('done', 'failed', 'canceled'):
            return

        template = forge_db.get_workflow_template(run['template_id'])
        if not template:
            forge_db.update_workflow_run(run_id, status='failed', error='模板不存在', finished_at=_now())
            return

        try:
            graph, _ = graph_for_template(template.get('definition') or {})
        except ValueError as e:
            forge_db.update_workflow_run(run_id, status='failed', error=str(e), finished_at=_now())
            return

        step_runs = forge_db.list_workflow_step_runs(run_id)

        if has_waiting_human(step_runs):
            if run['status'] != 'waiting_human':
                gate = next(s for s in step_runs if s.get('status') == 'waiting_human')
                forge_db.update_workflow_run(
                    run_id, status='waiting_human', current_step_id=gate['step_id'],
                )
            return

        _propagate_skips(run_id, graph)
        step_runs = forge_db.list_workflow_step_runs(run_id)

        if all_nodes_terminal(graph, step_runs):
            if any(s.get('status') == 'failed' for s in step_runs):
                forge_db.update_workflow_run(run_id, status='failed', finished_at=_now())
            else:
                forge_db.update_workflow_run(run_id, status='done', finished_at=_now(), current_step_id=None)
                run = forge_db.get_workflow_run(run_id)
                emit_event('workflow_done', run=run, schedule=_get_schedule_for_run(run))
            return

        runnable = find_runnable_nodes(graph, step_runs)
        if not runnable:
            pending = [s for s in step_runs if s.get('status') == 'pending']
            if pending:
                forge_db.update_workflow_run(
                    run_id, status='failed',
                    error='存在无法调度的 pending 节点（检查分支/环）',
                    finished_at=_now(),
                )
            else:
                forge_db.update_workflow_run(run_id, status='done', finished_at=_now(), current_step_id=None)
                run = forge_db.get_workflow_run(run_id)
                emit_event('workflow_done', run=run, schedule=_get_schedule_for_run(run))
            return

        step_id = runnable[0]
        node_def = _node_def(graph, step_id)
        step_run = forge_db.get_workflow_step_run(run_id, step_id)
        if not node_def or not step_run:
            forge_db.update_workflow_run(run_id, status='failed', error=f'缺少节点 {step_id}', finished_at=_now())
            return

        if step_run['status'] == 'pending':
            forge_db.update_workflow_run(run_id, status='running', current_step_id=step_id, started_at=_now())
            forge_db.update_workflow_step_run(run_id, step_id, status='running', started_at=_now())

        try:
            output, skipped = execute_step(run, node_def, step_run)
        except Exception as e:  # noqa: BLE001
            err = str(e)
            forge_db.update_workflow_step_run(run_id, step_id, status='failed', error=err, finished_at=_now())
            forge_db.update_workflow_run(run_id, status='failed', error=err, finished_at=_now())
            run = forge_db.get_workflow_run(run_id)
            emit_event('workflow_failed', run=run, schedule=_get_schedule_for_run(run),
                       step=step_run, extra={'message': err})
            return

        run = forge_db.get_workflow_run(run_id)
        context = _merge_step_output(run.get('context'), step_id, output)
        forge_db.update_workflow_run(run_id, context=context)

        child_job_id = output.get('job_id') if isinstance(output, dict) else None
        child_batch_id = output.get('batch_id') if isinstance(output, dict) else None

        if node_def['kind'] == 'gate_human' and not skipped:
            human_action = {
                'gate_type': output.get('gate_type'),
                'batch_id': child_batch_id,
                'instructions': output.get('instructions'),
            }
            forge_db.update_workflow_step_run(
                run_id, step_id,
                status='waiting_human',
                output=output,
                child_batch_id=child_batch_id,
                human_action=human_action,
                finished_at=None,
            )
            forge_db.update_workflow_run(run_id, status='waiting_human', current_step_id=step_id)
            run = forge_db.get_workflow_run(run_id)
            step = forge_db.get_workflow_step_run(run_id, step_id)
            emit_event(
                'waiting_human', run=run, schedule=_get_schedule_for_run(run), step=step,
                extra={'message': output.get('instructions')},
            )
            return

        if skipped:
            forge_db.update_workflow_step_run(
                run_id, step_id,
                status='skipped',
                output=output,
                child_job_id=child_job_id,
                child_batch_id=child_batch_id,
                finished_at=_now(),
            )
            run = forge_db.get_workflow_run(run_id)
            emit_event(
                'step_skipped', run=run, schedule=_get_schedule_for_run(run),
                step=step_run, extra={'message': output.get('reason', 'skipped')},
            )
            _propagate_skips(run_id, graph)
            if output.get('reason') == 'empty_result':
                run = forge_db.get_workflow_run(run_id)
                emit_event('workflow_done', run=run, schedule=_get_schedule_for_run(run),
                           extra={'message': '空结果，走空分支或跳过后续'})
            steps_done += 1
            continue

        forge_db.update_workflow_step_run(
            run_id, step_id,
            status='done',
            output=output,
            child_job_id=child_job_id,
            child_batch_id=child_batch_id,
            finished_at=_now(),
        )
        _propagate_skips(run_id, graph)
        steps_done += 1

    run = forge_db.get_workflow_run(run_id)
    if run and run['status'] == 'running':
        threading.Thread(
            target=_advance_thread,
            args=(run_id,),
            daemon=True,
            name=f'workflow-advance-{run_id}',
        ).start()


def _advance_thread(run_id):
    try:
        from flask import current_app
        app = current_app._get_current_object()
        with app.app_context():
            advance_run(run_id)
    except Exception:  # noqa: BLE001
        logger.debug('workflow advance thread failed', exc_info=True)


def start_custom_run(definition, params=None, *, name=None, created_by=None, app=None, save_template=True):
    """用自定义 definition（graph 或 steps）启动运行。"""
    import uuid

    norm = normalize_definition(definition)
    if not norm.get('steps'):
        raise ValueError('definition 无有效步骤')
    template_id = f"custom_{uuid.uuid4().hex[:10]}"
    if save_template:
        forge_db.upsert_workflow_template({
            'id': template_id,
            'name': name or '自定义编排',
            'description': '流程设计器创建',
            'definition': norm,
            'builtin': 0,
            'enabled': 1,
        })
    return start_run(
        template_id,
        params=params,
        name=name,
        created_by=created_by,
        app=app,
    )


def start_run(template_id, params=None, *, name=None, schedule_id=None, created_by=None, app=None):
    """创建并后台启动工作流运行。"""
    if not forge_db.schema_ready():
        raise RuntimeError('detforge 写库未初始化，请先建表')
    ensure_builtin_templates()

    template = forge_db.get_workflow_template(template_id)
    if not template or not template.get('enabled'):
        raise ValueError(f'工作流模板不存在或已禁用: {template_id}')

    params = dict(params or {})
    run_name = name or f"{template.get('name') or template_id}"
    run_id = forge_db.create_workflow_run({
        'template_id': template_id,
        'schedule_id': schedule_id,
        'name': run_name,
        'params': params,
        'created_by': created_by,
    })

    _, steps = graph_for_template(template.get('definition') or {})
    forge_db.insert_workflow_step_runs(run_id, steps)

    if app is None:
        from flask import current_app
        app = current_app._get_current_object()

    run = forge_db.get_workflow_run(run_id)
    schedule = _get_schedule_for_run(run)
    emit_event('workflow_started', run=run, schedule=schedule)

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(run_id, app),
        daemon=True,
        name=f'workflow-run-{run_id}',
    )
    with _thread_lock:
        _active_threads[run_id] = thread
    thread.start()
    return forge_db.get_workflow_run(run_id)


def _run_pipeline_thread(run_id, app):
    with app.app_context():
        try:
            advance_run(run_id, max_steps=50)
        except Exception as e:  # noqa: BLE001
            logger.error('工作流 #%s 异常: %s\n%s', run_id, e, traceback.format_exc())
            forge_db.update_workflow_run(run_id, status='failed', error=str(e), finished_at=_now())


def resume_run(run_id, *, app=None):
    """人工卡点完成后恢复。"""
    run = forge_db.get_workflow_run(run_id)
    if not run:
        raise ValueError('运行实例不存在')
    if run['status'] != 'waiting_human':
        raise ValueError(f"当前状态 {run['status']} 不可恢复")

    step_runs = forge_db.list_workflow_step_runs(run_id)
    gate = next((s for s in step_runs if s['status'] == 'waiting_human'), None)
    if not gate:
        raise ValueError('未找到等待中的步骤')

    batch_id = gate.get('child_batch_id')
    if batch_id:
        batch = forge_db.get_curation_batch(int(batch_id))
        if batch and batch.get('status') in ('created', 'exported'):
            raise ValueError('请先上传筛选后的 COCO JSON')

    forge_db.update_workflow_step_run(
        run_id, gate['step_id'],
        status='done',
        output={**(gate.get('output') or {}), 'resumed_at': _now()},
        finished_at=_now(),
    )
    forge_db.update_workflow_run(run_id, status='running')

    if app is None:
        from flask import current_app
        app = current_app._get_current_object()

    thread = threading.Thread(
        target=_run_pipeline_thread,
        args=(run_id, app),
        daemon=True,
        name=f'workflow-resume-{run_id}',
    )
    thread.start()
    return forge_db.get_workflow_run(run_id)


def on_curation_imported(batch_id):
    """COCO 导入后尝试自动恢复关联工作流。"""
    runs = forge_db.find_workflow_runs_waiting_on_batch(int(batch_id))
    resumed = []
    for run in runs:
        try:
            resume_run(run['id'])
            resumed.append(run['id'])
        except Exception as e:  # noqa: BLE001
            logger.info('自动恢复工作流 #%s 跳过: %s', run['id'], e)
    return resumed


def get_run_detail(run_id):
    run = forge_db.get_workflow_run(run_id)
    if not run:
        raise ValueError('运行实例不存在')
    steps = forge_db.list_workflow_step_runs(run_id)
    template = forge_db.get_workflow_template(run['template_id'])
    notifications = forge_db.list_workflow_notifications(limit=30, run_id=run_id)
    graph = None
    try:
        graph, _ = graph_for_template((template or {}).get('definition') or {})
    except ValueError:
        pass
    return {
        'run': run,
        'steps': steps,
        'template': template,
        'graph': graph,
        'notifications': notifications,
    }
