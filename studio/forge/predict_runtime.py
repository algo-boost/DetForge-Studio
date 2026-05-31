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
    use_subprocess = bool(python_exe and script and os.path.isfile(script))
    return {
        'detunify_studio_root': root,
        'predict_python_executable': python_exe,
        'predict_script': script,
        'predict_src_dir': predict_src,
        'use_subprocess': use_subprocess,
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


def run_batch_predict(payload, config=None, timeout=None):
    """子进程批量预测；返回 results 列表。失败抛 RuntimeError。"""
    settings = resolve_predict_settings(config)
    if not settings['use_subprocess']:
        raise RuntimeError('未配置 predict_python_executable 或 predict_script 不可用')

    python_exe = settings['predict_python_executable']
    script = settings['predict_script']

    with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False, encoding='utf-8') as tf:
        json.dump(payload, tf, ensure_ascii=False)
        payload_path = tf.name

    try:
        proc = subprocess.run(
            [python_exe, script, '--payload-file', payload_path],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=settings['detunify_studio_root'] or None,
        )
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or '').strip() or f'exit {proc.returncode}'
        raise RuntimeError(f'预测子进程失败: {err}')

    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'预测子进程输出非 JSON: {proc.stdout[:500]}') from e

    if not data.get('success'):
        raise RuntimeError(data.get('error') or '预测子进程返回 success=false')
    return data.get('results') or []


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
