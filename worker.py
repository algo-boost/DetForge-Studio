"""后台作业 worker。

- 轮询 detforge.job 中的 pending 作业，按 job_type 分发处理器。
- 任务级并发：启动 N 个 loop 线程，各自独立领取并执行作业（predict 处理器各自 load_model 一次）。
- 任务内并发：由处理器依据 job.intra_concurrency 决定（共享一次模型加载）。
- 续跑：处理器只取 status in (pending,running) 的 job_item；重启自动跳过 done。
- 心跳：每个运行中的作业由独立心跳线程刷新；超时的 running 作业被回收为 pending。

启动方式：
  1) Flask 启动时自动拉起（PID 文件防重复，见 maybe_start_in_process）。
  2) 命令行独立运行：python worker.py [--concurrency N] [--once]
"""
import argparse
import logging
import os
import sys
import threading
import time

if sys.platform == 'win32':
    fcntl = None  # Windows 无 fcntl，用 msvcrt 或 PID 检测代替
else:
    import fcntl

from studio.forge import forge_db
from studio.forge import forge_predict
from studio.forge import forge_manual_qc
from studio.sync import forge_sync

from studio.paths import APP_ROOT as BASE_DIR

PID_FILE = os.path.join(BASE_DIR, 'exports', 'worker.pid')

logger = logging.getLogger('detforge.worker')
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] worker %(message)s'))
    logger.addHandler(_h)
    logger.setLevel(os.environ.get('PC_WORKER_LOGLEVEL', 'INFO').upper())

HEARTBEAT_INTERVAL = 15          # 秒
STALE_TIMEOUT = 120              # 秒，超时回收 running 作业
POLL_INTERVAL = 3                # 秒，空闲轮询间隔
CLEANUP_INTERVAL = 86400           # 秒，孤儿客户图自动清理间隔（24h）
SUPPORTED_JOB_TYPES = ('predict', 'manual_qc_archive', 'manual_qc_export', 'dataset_sync')
PREDICT_JOB_TYPES = ('predict',)
IO_JOB_TYPES = ('dataset_sync', 'manual_qc_archive', 'manual_qc_export')

_manager = None
_manager_lock = threading.Lock()


def resolve_worker_lanes():
    """解析 worker 线程池：默认预测与数据同步各 1 槽，互不阻塞。

    PC_WORKER_CONCURRENCY=N  → N 个通用槽（兼容旧配置，所有类型争抢）。
    否则：
      PC_WORKER_PREDICT_SLOTS（默认 1）
      PC_WORKER_SYNC_SLOTS（默认 1，含 dataset_sync / manual_qc_*）
    """
    if os.environ.get('PC_WORKER_CONCURRENCY') is not None:
        n = max(1, int(os.environ.get('PC_WORKER_CONCURRENCY', '1')))
        return [{'name': 'generic', 'job_types': SUPPORTED_JOB_TYPES, 'slots': n}]

    predict_slots = max(0, int(os.environ.get('PC_WORKER_PREDICT_SLOTS', '1')))
    sync_slots = max(0, int(os.environ.get('PC_WORKER_SYNC_SLOTS', '1')))
    lanes = []
    if predict_slots:
        lanes.append({'name': 'predict', 'job_types': PREDICT_JOB_TYPES, 'slots': predict_slots})
    if sync_slots:
        lanes.append({'name': 'sync', 'job_types': IO_JOB_TYPES, 'slots': sync_slots})
    if not lanes:
        lanes.append({'name': 'generic', 'job_types': SUPPORTED_JOB_TYPES, 'slots': 1})
    return lanes


def _job_is_stopped(job_id):
    """作业被置为 paused / canceled 时返回 True，处理器据此优雅停止。"""
    job = forge_db.get_job(job_id)
    return (not job) or job.get('status') in ('paused', 'canceled')


def _run_heartbeat(job_id, worker_id, stop_event):
    while not stop_event.wait(HEARTBEAT_INTERVAL):
        try:
            forge_db.heartbeat(job_id, worker_id)
        except Exception:
            pass


def _dispatch(job, worker_id):
    stop_event = threading.Event()
    hb = threading.Thread(target=_run_heartbeat, args=(job['id'], worker_id, stop_event), daemon=True)
    hb.start()

    def stop_check():
        return _job_is_stopped(job['id'])

    def on_progress():
        try:
            forge_db.heartbeat(job['id'], worker_id)
            prog = forge_db.recompute_job_progress(job['id'])
            total = int(job.get('total') or 0)
            if not total:
                total = int(prog.get('done', 0)) + int(prog.get('failed', 0)) + int(prog.get('remaining', 0))
            if total > 0:
                done = int(prog.get('done', 0))
                failed = int(prog.get('failed', 0))
                min_iv = 3.0 if job.get('job_type') == 'predict' else 6.0
                job_log.append_throttled(
                    job['id'],
                    f'进度 {done + failed}/{total}（完成 {done}，失败 {failed}，剩余 {prog.get("remaining", 0)}）',
                    key='item_progress',
                    min_interval=min_iv,
                )
        except Exception:
            pass

    started = time.time()
    from studio.forge import job_log
    job_log.append(job['id'], f'开始作业 type={job.get("job_type")} name={job.get("name") or "—"}')
    logger.info('开始作业 #%s type=%s name=%s', job['id'], job.get('job_type'), job.get('name'))
    try:
        if job['job_type'] == 'predict':
            params = job.get('params') or {}
            if params.get('predict_mode') == 'platform_validation':
                from studio.forge import forge_platform_predict
                from server.core import load_config
                forge_platform_predict.run_platform_predict_job(
                    job, stop_check=stop_check, on_progress=on_progress,
                    config=load_config(),
                )
            else:
                forge_predict.run_predict_job(job, stop_check=stop_check, on_progress=on_progress)
        elif job['job_type'] == 'manual_qc_archive':
            _run_manual_qc_job(job, stop_check=stop_check, on_progress=on_progress)
        elif job['job_type'] == 'manual_qc_export':
            _run_manual_qc_export_job(job, on_progress=on_progress)
        elif job['job_type'] == 'dataset_sync':
            forge_sync.run_dataset_sync_job(job, stop_check=stop_check, on_progress=on_progress)
        else:
            forge_db.finish_job(job['id'], status='failed', error=f"未知 job_type: {job['job_type']}")
            return

        progress = forge_db.recompute_job_progress(job['id'])
        latest = forge_db.get_job(job['id'])
        if latest and latest.get('status') == 'canceled':
            return
        if latest and latest.get('status') == 'paused':
            return
        if progress.get('remaining', 0) > 0:
            # 被停止但未取消：留待续跑
            forge_db.update_job(job['id'], status='pending', worker_id=None)
        elif progress.get('failed', 0) > 0 and progress.get('done', 0) == 0:
            forge_db.finish_job(job['id'], status='failed', error='全部作业项失败')
        else:
            forge_db.finish_job(job['id'], status='done')
        elapsed = time.time() - started
        job_log.append(job['id'], f'作业结束 status={forge_db.get_job(job["id"]).get("status")} 耗时 {elapsed:.1f}s')
        logger.info('结束作业 #%s 耗时 %.1fs', job['id'], elapsed)
    except Exception as e:  # noqa: BLE001
        import traceback
        tb = traceback.format_exc()
        job_log.append(job['id'], f'作业异常: {type(e).__name__}: {e}')
        for line in tb.strip().splitlines():
            job_log.append(job['id'], f'  {line}')
        logger.exception('作业 #%s 异常: %s', job['id'], e)
        forge_db.finish_job(job['id'], status='failed', error=str(e))
    finally:
        stop_event.set()


def _run_manual_qc_job(job, stop_check=None, on_progress=None):
    """作业化的人工质检归档（批量条目放在 params.entries）。"""
    params = job.get('params') or {}
    entries = params.get('entries') or []
    batch_id = params.get('batch_id')
    items = forge_db.pending_items(job['id'])
    by_ref = {str(i): e for i, e in enumerate(entries)}
    for item in items:
        if stop_check and stop_check():
            break
        forge_db.mark_item_running(item['id'])
        entry = by_ref.get(item['ref_key']) or {'product_no': item['ref_key']}
        try:
            res = forge_manual_qc.archive_one(
                product_no=entry.get('product_no'),
                customer_img_path=entry.get('customer_img_path'),
                batch_id=batch_id, note=entry.get('note'),
                position=entry.get('position'),
                defect_type=entry.get('defect_type'),
                qc_category=entry.get('qc_category'),
                matched_detail_id=entry.get('matched_detail_id'),
                no_match=entry.get('no_match', False),
            )
            forge_db.mark_item_done(item['id'], result_ref=res.get('id'))
        except Exception as e:  # noqa: BLE001
            forge_db.mark_item_failed(item['id'], error=str(e))
        forge_db.recompute_job_progress(job['id'])
        if on_progress:
            on_progress()


def _run_manual_qc_export_job(job, on_progress=None):
    """作业化的人工质检导出（参数在 params.export，结果回写 params.result）。"""
    params = job.get('params') or {}
    export_params = params.get('export') or {}
    items = forge_db.pending_items(job['id'])
    item = items[0] if items else None
    if item:
        forge_db.mark_item_running(item['id'])
    result = forge_manual_qc.export_records(**export_params)
    new_params = dict(params)
    new_params['result'] = result
    import json as _json
    forge_db.update_job(job['id'], params=_json.dumps(new_params, ensure_ascii=False))
    if item:
        forge_db.mark_item_done(item['id'])
    forge_db.recompute_job_progress(job['id'])
    if on_progress:
        on_progress()


class WorkerManager:
    def __init__(self, lanes=None, concurrency=None, worker_id=None):
        if concurrency is not None:
            lanes = [{'name': 'generic', 'job_types': SUPPORTED_JOB_TYPES, 'slots': max(1, int(concurrency))}]
        self.lanes = lanes or resolve_worker_lanes()
        self.worker_id = worker_id or f'worker-{os.getpid()}'
        self.stop_event = threading.Event()
        self.threads = []
        self._schema_ok = False

    @property
    def concurrency(self):
        return sum(int(lane.get('slots') or 0) for lane in self.lanes)

    def _ensure_schema_once(self):
        if self._schema_ok:
            return True
        try:
            forge_db.ensure_schema()
            self._schema_ok = True
        except Exception:
            self._schema_ok = False
        return self._schema_ok

    def _loop(self, lane_name, job_types, slot_in_lane, is_primary=False):
        worker_id = f'{self.worker_id}#{lane_name}-{slot_in_lane}'
        last_reclaim = 0.0
        last_cleanup = 0.0
        while not self.stop_event.is_set():
            if not self._ensure_schema_once():
                self.stop_event.wait(POLL_INTERVAL)
                continue
            now = time.time()
            if is_primary and now - last_reclaim > STALE_TIMEOUT / 2:
                try:
                    forge_db.reclaim_stale_jobs(STALE_TIMEOUT)
                except Exception:
                    pass
                last_reclaim = now
            if is_primary and now - last_cleanup > CLEANUP_INTERVAL:
                try:
                    r = forge_manual_qc.cleanup_orphan_uploads(dry_run=False)
                    if r.get('deleted'):
                        logger.info('自动清理未引用客户图 %s 个', r['deleted'])
                except Exception:
                    pass
                last_cleanup = now
            try:
                job = forge_db.claim_next_job(worker_id, job_types)
            except Exception:
                job = None
            if not job:
                self.stop_event.wait(POLL_INTERVAL)
                continue
            _dispatch(job, worker_id)

    def start(self):
        is_first = True
        for lane in self.lanes:
            name = lane['name']
            job_types = lane['job_types']
            for slot in range(int(lane.get('slots') or 0)):
                primary = is_first
                is_first = False
                t = threading.Thread(
                    target=self._loop,
                    args=(name, job_types, slot, primary),
                    daemon=True,
                )
                t.start()
                self.threads.append(t)
        return self

    def stop(self):
        self.stop_event.set()

    def run_once(self):
        """单次领取并执行一个作业（测试 / 命令行 --once）。"""
        if not self._ensure_schema_once():
            return False
        job = forge_db.claim_next_job(self.worker_id, SUPPORTED_JOB_TYPES)
        if not job:
            return False
        _dispatch(job, self.worker_id)
        return True


# ── Flask 自动拉起（PID 防重复）──────────────────────────────────────

def _read_pid():
    try:
        with open(PID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def _pid_alive(pid):
    if not pid:
        return False
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return False
    if sys.platform == 'win32':
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if handle:
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _try_exclusive_lock(lock_f):
    """跨平台非阻塞文件锁（Flask reloader 双进程防重复拉起 worker）。"""
    try:
        if fcntl is not None:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(lock_f.fileno(), msvcrt.LK_NBLCK, 1)
            return True
    except OSError:
        return False
    return False


def _release_lock(lock_f):
    if not lock_f:
        return
    try:
        if fcntl is not None:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)
        elif sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(lock_f.fileno(), msvcrt.LK_UNLCK, 1)
        lock_f.close()
    except Exception:
        pass


def maybe_start_in_process(concurrency=None):
    """Flask 启动调用：若无存活 worker 则在本进程内拉起。可用 PC_NO_WORKER=1 禁用。"""
    global _manager
    if os.environ.get('PC_NO_WORKER') == '1':
        return None
    if os.environ.get('WERKZEUG_RUN_MAIN') == 'false':
        return None
    with _manager_lock:
        if _manager is not None:
            return _manager
        os.makedirs(os.path.dirname(PID_FILE), exist_ok=True)
        lock_path = PID_FILE + '.lock'
        lock_f = None
        try:
            lock_f = open(lock_path, 'w')
            if not _try_exclusive_lock(lock_f):
                existing = _read_pid()
                if _pid_alive(existing):
                    logger.info('已有存活 worker (pid=%s)，本进程不再拉起', existing)
                return None
        except OSError:
            existing = _read_pid()
            if _pid_alive(existing):
                logger.info('已有存活 worker (pid=%s)，本进程不再拉起', existing)
            return None
        existing = _read_pid()
        if _pid_alive(existing) and existing != os.getpid():
            logger.info('已有存活 worker (pid=%s)，本进程不再拉起', existing)
            _release_lock(lock_f)
            return None
        try:
            with open(PID_FILE, 'w') as f:
                f.write(str(os.getpid()))
        except Exception:
            pass
        lanes = resolve_worker_lanes()
        lane_summary = ', '.join(f"{l['name']}×{l['slots']}" for l in lanes)
        logger.info('在 Flask 进程内启动 worker pid=%s lanes=[%s]', os.getpid(), lane_summary)
        if concurrency is not None:
            _manager = WorkerManager(concurrency=concurrency).start()
        else:
            _manager = WorkerManager(lanes=lanes).start()
        return _manager


def shutdown_in_process_worker():
    """Flask 关闭时停止 in-process worker 线程。"""
    global _manager
    with _manager_lock:
        if _manager is not None:
            _manager.stop()
            _manager = None


def main():
    parser = argparse.ArgumentParser(description='DetForge 后台作业 worker')
    parser.add_argument(
        '--concurrency', type=int, default=None,
        help='通用槽位数（覆盖分 lane 默认；与 PC_WORKER_CONCURRENCY 等效）',
    )
    parser.add_argument('--predict-slots', type=int, default=None, help='预测专用槽（默认 1）')
    parser.add_argument('--sync-slots', type=int, default=None, help='同步/I/O 槽（默认 1）')
    parser.add_argument('--once', action='store_true', help='只执行一个作业后退出')
    args = parser.parse_args()

    if args.concurrency is not None:
        os.environ['PC_WORKER_CONCURRENCY'] = str(args.concurrency)
    if args.predict_slots is not None:
        os.environ['PC_WORKER_PREDICT_SLOTS'] = str(args.predict_slots)
    if args.sync_slots is not None:
        os.environ['PC_WORKER_SYNC_SLOTS'] = str(args.sync_slots)

    lanes = resolve_worker_lanes()
    manager = WorkerManager(lanes=lanes) if args.concurrency is None else WorkerManager(concurrency=args.concurrency)
    if args.once:
        ok = manager.run_once()
        print('已处理一个作业' if ok else '无待处理作业')
        return
    lane_summary = ', '.join(f"{l['name']}×{l['slots']}" for l in manager.lanes)
    print(f'worker 启动，lanes=[{lane_summary}]，Ctrl-C 退出')
    manager.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        manager.stop()
        try:
            from studio.lifecycle import shutdown
            shutdown('worker-interrupt')
        except Exception:
            pass
        print('worker 已停止')


if __name__ == '__main__':
    main()
