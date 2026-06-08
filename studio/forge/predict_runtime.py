"""预测运行时：解析 DetUnify 路径 / Python 解释器，并通过子进程调用预测脚本。

当 config.predict_python_executable 非空时，DetForge 不 import torch，而是：

    {predict_python_executable} {predict_script} --payload-file {tmp.json}

payload 结构::

    {
      "model": {"checkpoint_path", "framework", "sub_type"},
      "device": "cuda:0",
      "threshold": 0.5,
      "max_size": 1536,
      "images": [{"path": "/a.jpg"}, ...]
    }

脚本 stdout 返回 ``{"success": true, "results": [...]}``。
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile

from studio.paths import (
    APP_ROOT,
    default_detunify_studio_root,
    resolve_config_path,
)

DEFAULT_WORKER_REL = os.path.join('scripts', 'predict_job_worker.py')
DEFAULT_PREDICT_SRC_REL = os.path.join('src', 'predict')


def default_detunify_root():
    """未配置时：发行包 tools/ → monorepo sibling。"""
    return default_detunify_studio_root()


def _default_predict_python_exe():
    """子进程预测解释器：优先环境变量，否则当前解释器（独立进程，避免 worker 线程 import mmdet）。"""
    import sys

    env = str(os.environ.get('PC_PREDICT_PYTHON') or '').strip()
    if env and os.path.isfile(env):
        return env
    exe = str(sys.executable or '').strip()
    return exe if exe and os.path.isfile(exe) else ''


def resolve_predict_settings(config=None):
    """从 config 解析预测相关路径；返回 dict。"""
    from server.core import load_config

    cfg = config or load_config()
    config_root = str(cfg.get('detunify_studio_root') or '').strip()
    if config_root:
        root = resolve_config_path(config_root, must_exist=True) or ''
    else:
        root = default_detunify_root()
    python_exe = str(cfg.get('predict_python_executable') or '').strip()
    if python_exe:
        resolved_py = resolve_config_path(python_exe, must_exist=True)
        if resolved_py:
            python_exe = resolved_py
    script_cfg = str(cfg.get('predict_script') or '').strip()
    if script_cfg:
        script = resolve_config_path(script_cfg, must_exist=True) or ''
    else:
        script = ''
    if root and not script:
        script = os.path.join(root, DEFAULT_WORKER_REL)
    predict_src = os.path.join(root, DEFAULT_PREDICT_SRC_REL) if root else ''
    script_ok = bool(script and os.path.isfile(script))
    # 未显式配置解释器时：若 predict_job_worker 可用，默认走子进程（同机多进程，规避线程内加载 torch/mmdet）
    force_inprocess = os.environ.get('PC_FORCE_INPROCESS_PREDICT', '').strip() in ('1', 'true', 'yes')
    if not python_exe and script_ok and not force_inprocess:
        python_exe = _default_predict_python_exe()
    use_subprocess = bool(python_exe and script_ok and not force_inprocess)
    return {
        'detunify_studio_root': root,
        'predict_python_executable': python_exe,
        'predict_script': script,
        'predict_src_dir': predict_src,
        'use_subprocess': use_subprocess,
        'predict_subprocess_auto': bool(use_subprocess and not str(cfg.get('predict_python_executable') or '').strip()),
    }


def parse_subprocess_stdout(stdout):
    """从子进程 stdout 解析 JSON；容忍 ml_backend 等在 JSON 前的 print（如尺寸日志）。"""
    text = (stdout or '').strip()
    if not text:
        raise ValueError('子进程 stdout 为空')

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    for line in reversed([ln.strip() for ln in text.splitlines() if ln.strip()]):
        if not line.startswith('{'):
            continue
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue

    start = -1
    for marker in ('{"success"', '{"ok"', '{"framework"'):
        idx = text.find(marker)
        if idx >= 0 and (start < 0 or idx < start):
            start = idx
    if start < 0:
        start = text.find('{')
    if start >= 0:
        try:
            obj, _end = json.JSONDecoder().raw_decode(text, start)
            return obj
        except json.JSONDecodeError:
            pass

    raise ValueError(f'无法从 stdout 解析 JSON: {text[:500]}')


def validate_predict_settings(config=None):
    """供设置页展示的检查结果。"""
    s = resolve_predict_settings(config)
    checks = {
        'detunify_studio_root_exists': bool(s['detunify_studio_root'] and os.path.isdir(s['detunify_studio_root'])),
        'predict_script_exists': bool(s['predict_script'] and os.path.isfile(s['predict_script'])),
        'predict_python_configured': bool(s['predict_python_executable']),
        'predict_python_exists': bool(
            s['predict_python_executable'] and os.path.isfile(s['predict_python_executable'])
        ),
        'use_subprocess': s['use_subprocess'],
    }
    return s, checks


def _log_stream_line(log_line, tag, text):
    """写入作业日志；超大 JSON 结果行仅记长度，避免撑爆日志文件。"""
    if not log_line:
        return
    s = (text or '').strip()
    if not s:
        return
    if tag == 'stdout' and len(s) > 800 and s.lstrip().startswith('{'):
        log_line(f'[stdout] (省略 JSON 结果行，{len(s)} 字符)')
        return
    log_line(f'[{tag}] {s}')


def _log_stdout_tail(log_line, stdout, max_chars=4000):
    if not log_line or not stdout:
        return
    text = stdout.strip()
    if not text:
        return
    if len(text) <= max_chars:
        for ln in text.splitlines():
            _log_stream_line(log_line, 'stdout', ln)
        return
    log_line(f'[stdout] (失败/异常时输出摘要，共 {len(text)} 字符)')
    for ln in text[-max_chars:].splitlines()[-40:]:
        _log_stream_line(log_line, 'stdout', ln)


def run_batch_predict(payload, config=None, timeout=None, log_line=None):
    """子进程批量预测；返回 results 列表。失败抛 RuntimeError。

    log_line: 可选回调，接收子进程 stderr/stdout 行（用于作业详情页实时日志）。
    """
    import threading

    settings = resolve_predict_settings(config)
    if not settings['use_subprocess']:
        raise RuntimeError('未配置 predict_python_executable 或 predict_script 不可用')

    python_exe = settings['predict_python_executable']
    script = settings['predict_script']
    cwd = settings['detunify_studio_root'] or None
    images = payload.get('images') or []
    model_cfg = payload.get('model') or {}

    if log_line:
        log_line(f'[cmd] {python_exe} {script} --payload-file <tmp>')
        if cwd:
            log_line(f'[cwd] {cwd}')
        log_line(
            f'[payload] images={len(images)} device={payload.get("device")} '
            f'threshold={payload.get("threshold")} max_size={payload.get("max_size")} '
            f'framework={model_cfg.get("framework")} sub_type={model_cfg.get("sub_type")}'
        )
        ckpt = model_cfg.get('checkpoint_path') or ''
        if ckpt:
            log_line(f'[payload] checkpoint={ckpt}')

    from studio.paths import app_temp_dir
    from studio.process_registry import kill_process_tree, register_child, unregister_child

    with tempfile.NamedTemporaryFile(
        'w', suffix='.json', delete=False, encoding='utf-8', dir=app_temp_dir(),
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name

    stdout_lines = []
    stderr_lines = []
    proc = None
    returncode = 1

    def _drain(stream, buf, tag):
        if not stream:
            return
        try:
            for line in stream:
                s = line.rstrip('\n\r')
                if not s:
                    continue
                buf.append(s)
                _log_stream_line(log_line, tag, s)
        finally:
            try:
                stream.close()
            except Exception:
                pass

    try:
        proc = subprocess.Popen(
            [python_exe, script, '--payload-file', payload_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=cwd,
        )
        register_child(proc.pid, 'predict_batch')

        out_thread = threading.Thread(
            target=_drain, args=(proc.stdout, stdout_lines, 'stdout'), daemon=True,
        )
        err_thread = threading.Thread(
            target=_drain, args=(proc.stderr, stderr_lines, 'stderr'), daemon=True,
        )
        out_thread.start()
        err_thread.start()
        try:
            returncode = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            if proc:
                kill_process_tree(proc.pid)
            proc.wait()
            out_thread.join(timeout=2.0)
            err_thread.join(timeout=2.0)
            if log_line:
                log_line(f'[error] 预测子进程超时（>{timeout}s）')
            raise RuntimeError(f'预测子进程超时（>{timeout}s）')
        out_thread.join(timeout=5.0)
        err_thread.join(timeout=5.0)
        stdout = '\n'.join(stdout_lines)
        stderr_text = '\n'.join(stderr_lines)
    finally:
        if proc is not None:
            unregister_child(proc.pid)
            if proc.poll() is None:
                kill_process_tree(proc.pid)
        try:
            os.unlink(payload_path)
        except OSError:
            pass

    if log_line:
        log_line(f'[exit] returncode={returncode} stdout_lines={len(stdout_lines)} stderr_lines={len(stderr_lines)}')

    if returncode != 0:
        err = (stderr_text or stdout or '').strip() or f'exit {returncode}'
        _log_stdout_tail(log_line, stdout)
        if stderr_text and log_line:
            for ln in stderr_text.splitlines()[-30:]:
                _log_stream_line(log_line, 'stderr', ln)
        raise RuntimeError(f'预测子进程失败: {err[:2000]}')

    try:
        data = parse_subprocess_stdout(stdout)
    except ValueError as e:
        _log_stdout_tail(log_line, stdout)
        if log_line:
            log_line(f'[error] 解析子进程 JSON 失败: {e}')
        raise RuntimeError(f'预测子进程输出非 JSON: {e}') from e

    if not data.get('success'):
        err = data.get('error') or '预测子进程返回 success=false'
        trace = data.get('trace') or ''
        if log_line:
            log_line(f'[error] {err}')
            if trace:
                for ln in str(trace).splitlines()[:40]:
                    log_line(f'[trace] {ln}')
        raise RuntimeError(err)

    results = data.get('results') or []
    if log_line:
        ok_n = sum(1 for r in results if r.get('ok'))
        fail_n = len(results) - ok_n
        log_line(f'[done] 子进程返回 results={len(results)}（成功 {ok_n}，失败 {fail_n}）')
    return results


_DETECT_SNIPPET = (
    'import json, sys\n'
    'sys.path.insert(0, sys.argv[1])\n'
    'from predict import detect_model_type\n'
    'fw, sub = detect_model_type(sys.argv[2])\n'
    'print(json.dumps({"framework": fw, "sub_type": sub}, ensure_ascii=False))\n'
)


def detect_model_framework(checkpoint_path, config=None, timeout=120):
    """从权重文件探测 (framework, sub_type)；失败返回 ('', None)。"""
    path = str(checkpoint_path or '').strip()
    if not path or not os.path.isfile(path):
        return '', None

    settings = resolve_predict_settings(config)
    predict_src = settings.get('predict_src_dir') or ''
    if not predict_src or not os.path.isdir(predict_src):
        fallback_root = default_detunify_root()
        predict_src = os.path.join(fallback_root, DEFAULT_PREDICT_SRC_REL) if fallback_root else ''
    if not predict_src or not os.path.isdir(predict_src):
        return '', None

    python_exe = str(settings.get('predict_python_executable') or '').strip()
    if not python_exe or not os.path.isfile(python_exe):
        import sys
        python_exe = sys.executable

    try:
        proc = subprocess.run(
            [python_exe, '-c', _DETECT_SNIPPET, predict_src, path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=settings.get('detunify_studio_root') or default_detunify_root() or None,
        )
    except subprocess.TimeoutExpired:
        return '', None
    except OSError:
        return '', None

    if proc.returncode != 0:
        return '', None
    stdout = (proc.stdout or '').strip()
    if not stdout:
        return '', None
    line = stdout.splitlines()[-1]
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return '', None
    framework = str(data.get('framework') or '').strip()
    sub_type = data.get('sub_type')
    if sub_type is not None:
        sub_type = str(sub_type).strip() or None
    return framework, sub_type


def run_health_check(model, device=None, threshold=0.5, max_size=1536, config=None):
    """子进程健康检查；返回 {ok, error?, framework, device}。"""
    settings = resolve_predict_settings(config)
    if not settings['use_subprocess']:
        raise RuntimeError('未配置子进程预测环境')
    payload = {
        'mode': 'health_check',
        'model': {
            'checkpoint_path': model['checkpoint_path'],
            'framework': model.get('framework'),
            'sub_type': model.get('sub_type'),
        },
        'device': device or 'cuda:0',
        'threshold': threshold,
        'max_size': max_size,
    }
    import json
    import tempfile

    from studio.paths import app_temp_dir
    from studio.process_registry import kill_process_tree, register_child, unregister_child

    with tempfile.NamedTemporaryFile(
        'w', suffix='.json', delete=False, encoding='utf-8', dir=app_temp_dir(),
    ) as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name
    proc = None
    stdout = ''
    try:
        proc = subprocess.Popen(
            [settings['predict_python_executable'], settings['predict_script'], '--payload-file', payload_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=settings['detunify_studio_root'] or None,
        )
        register_child(proc.pid, 'predict_health')
        stdout, stderr_text = proc.communicate()
        if proc.returncode != 0:
            err = (stderr_text or stdout or '').strip()
            return {'ok': False, 'error': err or f'exit {proc.returncode}', 'device': payload['device']}
    finally:
        if proc is not None:
            unregister_child(proc.pid)
            if proc.poll() is None:
                kill_process_tree(proc.pid)
        try:
            os.unlink(payload_path)
        except OSError:
            pass
    try:
        data = parse_subprocess_stdout(stdout)
    except ValueError as e:
        return {'ok': False, 'error': str(e), 'device': payload['device']}
    return {
        'ok': bool(data.get('ok')),
        'error': data.get('error'),
        'framework': model.get('framework'),
        'device': payload['device'],
    }
