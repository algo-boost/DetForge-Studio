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

from studio.paths import PROJECT_ROOT

DEFAULT_WORKER_REL = os.path.join('scripts', 'predict_job_worker.py')
DEFAULT_PREDICT_SRC_REL = os.path.join('src', 'predict')


def default_detunify_root():
    """未配置时尝试 sibling DetUnify-Studio。"""
    sibling = os.path.normpath(os.path.join(PROJECT_ROOT, '..', 'DetUnify-Studio'))
    if os.path.isdir(sibling):
        return sibling
    return ''


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
    root = str(cfg.get('detunify_studio_root') or '').strip() or default_detunify_root()
    python_exe = str(cfg.get('predict_python_executable') or '').strip()
    script = str(cfg.get('predict_script') or '').strip()
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

    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name

    try:
        proc = subprocess.Popen(
            [python_exe, script, '--payload-file', payload_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=settings['detunify_studio_root'] or None,
        )

        def _drain(stream, prefix=''):
            if not stream:
                return
            for line in stream:
                s = line.rstrip()
                if s and log_line:
                    log_line(f'{prefix}{s}' if prefix else s)

        err_thread = threading.Thread(target=_drain, args=(proc.stderr, ''), daemon=True)
        err_thread.start()
        try:
            stdout, _stderr_rest = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise RuntimeError(f'预测子进程超时（>{timeout}s）')
        err_thread.join(timeout=1.0)
        returncode = proc.returncode
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass

    if returncode != 0:
        err = (stdout or '').strip() or f'exit {returncode}'
        raise RuntimeError(f'预测子进程失败: {err}')

    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'预测子进程输出非 JSON: {(stdout or "")[:500]}') from e

    if not data.get('success'):
        raise RuntimeError(data.get('error') or '预测子进程返回 success=false')
    return data.get('results') or []


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

    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name
    try:
        proc = subprocess.run(
            [settings['predict_python_executable'], settings['predict_script'], '--payload-file', payload_path],
            capture_output=True,
            text=True,
            cwd=settings['detunify_studio_root'] or None,
        )
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip()
        return {'ok': False, 'error': err or f'exit {proc.returncode}', 'device': payload['device']}
    data = json.loads(proc.stdout)
    return {
        'ok': bool(data.get('ok')),
        'error': data.get('error'),
        'framework': model.get('framework'),
        'device': payload['device'],
    }
