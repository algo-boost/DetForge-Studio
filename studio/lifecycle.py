"""服务启动 / 关闭生命周期：子进程清理、作业中断与续跑。"""
from __future__ import annotations

import atexit
import logging
import signal
import threading
import time

logger = logging.getLogger('detforge.lifecycle')

_shutdown_lock = threading.Lock()
_shutdown_done = False


def startup() -> None:
    """Flask/worker 启动前：清理遗留子进程，暂停未完成作业等待用户确认。"""
    from studio.process_registry import cleanup_orphans_on_startup
    from studio.forge import forge_db

    n_child = cleanup_orphans_on_startup()
    if n_child:
        logger.info('启动时已终止 %s 个遗留子进程', n_child)
    n_jobs = forge_db.isolate_incomplete_jobs_on_startup()
    if n_jobs:
        logger.info('启动时已暂停 %s 个未完成作业，等待用户确认是否续跑', n_jobs)


def shutdown(reason: str = 'shutdown') -> None:
    """服务关闭：停止 worker、暂停在跑作业、终止登记子进程。"""
    global _shutdown_done
    with _shutdown_lock:
        if _shutdown_done:
            return
        _shutdown_done = True

    logger.info('服务关闭 (%s)：暂停作业并终止子进程 …', reason)

    try:
        from worker import shutdown_in_process_worker
        shutdown_in_process_worker()
    except Exception as e:  # noqa: BLE001
        logger.warning('停止 in-process worker 失败: %s', e)

    try:
        from studio.forge import forge_db
        n = forge_db.pause_active_jobs_for_service_stop(reason=reason)
        if n:
            logger.info('已暂停 %s 个在跑/排队作业', n)
    except Exception as e:  # noqa: BLE001
        logger.warning('暂停作业失败: %s', e)

    try:
        from studio.process_registry import kill_all_registered
        n = kill_all_registered()
        if n:
            logger.info('已终止 %s 个子进程', n)
    except Exception as e:  # noqa: BLE001
        logger.warning('终止子进程失败: %s', e)


def install_hooks() -> None:
    """注册 atexit / 信号处理（幂等）。"""
    atexit.register(lambda: shutdown('atexit'))

    def _handle(signum, _frame):
        shutdown(f'signal:{signum}')
        time.sleep(0.2)
        raise SystemExit(0)

    for sig in (getattr(signal, 'SIGTERM', None), getattr(signal, 'SIGINT', None)):
        if sig is None:
            continue
        try:
            signal.signal(sig, _handle)
        except (ValueError, OSError):
            pass
