"""工作流定时调度器（cron）。"""
from __future__ import annotations

import logging
import threading
import time

from studio.forge import forge_db
from studio.forge.workflow_engine import start_run
from studio.forge.workflow_templates import ensure_builtin_templates, ensure_default_schedules
from studio.timezone_util import format_datetime, format_now, now_local

logger = logging.getLogger('detforge.workflow.scheduler')

_scheduler_thread = None
_scheduler_lock = threading.Lock()
POLL_INTERVAL = 60


def _parse_cron_field(field, min_v, max_v):
    field = str(field).strip()
    if field == '*':
        return None
    values = set()
    for part in field.split(','):
        part = part.strip()
        if '/' in part:
            base, step = part.split('/', 1)
            step = int(step)
            if base == '*':
                start, end = min_v, max_v
            elif '-' in base:
                a, b = base.split('-', 1)
                start, end = int(a), int(b)
            else:
                start, end = int(base), max_v
            for v in range(start, end + 1, step):
                if min_v <= v <= max_v:
                    values.add(v)
        elif '-' in part:
            a, b = part.split('-', 1)
            for v in range(int(a), int(b) + 1):
                if min_v <= v <= max_v:
                    values.add(v)
        else:
            v = int(part)
            if min_v <= v <= max_v:
                values.add(v)
    return values or None


def compute_next_run(cron_expr, timezone='Asia/Shanghai', *, after=None):
    """计算 cron 下次执行时间（5 段：分 时 日 月 周）。"""
    parts = str(cron_expr).split()
    if len(parts) != 5:
        raise ValueError(f'cron 须 5 段: {cron_expr}')
    mins = _parse_cron_field(parts[0], 0, 59)
    hours = _parse_cron_field(parts[1], 0, 23)
    days = _parse_cron_field(parts[2], 1, 31)
    months = _parse_cron_field(parts[3], 1, 12)
    weekdays = _parse_cron_field(parts[4], 0, 6)

    now = after or now_local()
    if timezone and hasattr(now, 'astimezone'):
        try:
            from zoneinfo import ZoneInfo
            now = now.astimezone(ZoneInfo(timezone))
        except Exception:  # noqa: BLE001
            pass

    candidate = now.replace(second=0, microsecond=0) + __import__('datetime').timedelta(minutes=1)
    limit = candidate + __import__('datetime').timedelta(days=366)
    while candidate < limit:
        if months and candidate.month not in months:
            candidate += __import__('datetime').timedelta(minutes=1)
            continue
        if days and candidate.day not in days:
            candidate += __import__('datetime').timedelta(minutes=1)
            continue
        if weekdays is not None and candidate.weekday() not in _cron_weekday_map(weekdays):
            candidate += __import__('datetime').timedelta(minutes=1)
            continue
        if hours and candidate.hour not in hours:
            candidate += __import__('datetime').timedelta(minutes=1)
            continue
        if mins and candidate.minute not in mins:
            candidate += __import__('datetime').timedelta(minutes=1)
            continue
        return format_datetime(candidate)
    raise ValueError('无法在一年内找到下次执行时间')


def _cron_weekday_map(weekdays):
    """cron 周日=0 → Python Monday=0 转换。"""
    out = set()
    for w in weekdays:
        out.add((int(w) - 1) % 7 if int(w) >= 1 else 6)
    return out


def _trigger_schedule(schedule, app):
    if schedule.get('mutex') and forge_db.has_active_workflow_run_for_schedule(schedule['id']):
        logger.info('调度 #%s 跳过：上次运行未完成', schedule['id'])
        nra = compute_next_run(schedule['cron_expr'], schedule.get('timezone'))
        forge_db.update_workflow_schedule(schedule['id'], next_run_at=nra, last_triggered_at=format_now())
        return None

    params = schedule.get('params') or {}
    if schedule['template_id'] == 'weekly_predict_eval' and not params.get('model_id'):
        logger.warning('调度 #%s 跳过：weekly_predict_eval 未配置 model_id', schedule['id'])
        nra = compute_next_run(schedule['cron_expr'], schedule.get('timezone'))
        forge_db.update_workflow_schedule(schedule['id'], next_run_at=nra, last_triggered_at=format_now())
        return None

    run = start_run(
        schedule['template_id'],
        params=params,
        name=schedule.get('name'),
        schedule_id=schedule['id'],
        created_by='scheduler',
        app=app,
    )
    nra = compute_next_run(schedule['cron_expr'], schedule.get('timezone'))
    forge_db.update_workflow_schedule(
        schedule['id'],
        last_run_id=run['id'],
        last_triggered_at=format_now(),
        next_run_at=nra,
    )
    return run


def tick(app=None):
    """检查并触发到期调度。"""
    if not forge_db.schema_ready():
        return 0
    ensure_builtin_templates()
    now_str = format_now()
    due = forge_db.list_due_workflow_schedules(now_str)
    n = 0
    for sched in due:
        try:
            if app is None:
                from flask import current_app
                app = current_app._get_current_object()
            _trigger_schedule(sched, app)
            n += 1
        except Exception as e:  # noqa: BLE001
            logger.error('触发调度 #%s 失败: %s', sched['id'], e)
            try:
                nra = compute_next_run(sched['cron_expr'], sched.get('timezone'))
                forge_db.update_workflow_schedule(sched['id'], next_run_at=nra)
            except Exception:  # noqa: BLE001
                pass
    return n


def _scheduler_loop(app):
    while True:
        try:
            with app.app_context():
                tick(app)
        except Exception as e:  # noqa: BLE001
            logger.warning('调度 tick 异常: %s', e)
        time.sleep(POLL_INTERVAL)


def init_workflow_scheduler(app):
    """启动后台调度线程（幂等）。"""
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread and _scheduler_thread.is_alive():
            return
        try:
            with app.app_context():
                ensure_builtin_templates()
                ensure_default_schedules()
                for sched in forge_db.list_workflow_schedules():
                    if sched.get('enabled') and not sched.get('next_run_at'):
                        nra = compute_next_run(sched['cron_expr'], sched.get('timezone'))
                        forge_db.update_workflow_schedule(sched['id'], next_run_at=nra)
        except Exception as e:  # noqa: BLE001
            logger.warning('初始化调度失败: %s', e)

        _scheduler_thread = threading.Thread(
            target=_scheduler_loop,
            args=(app,),
            daemon=True,
            name='workflow-scheduler',
        )
        _scheduler_thread.start()
        logger.info('工作流调度器已启动（间隔 %ss）', POLL_INTERVAL)
