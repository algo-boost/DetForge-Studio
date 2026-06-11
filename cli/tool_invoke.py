"""iisp tool invoke / run — Tool Contract v1 CLI 入口。"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

from capabilities.base import RunContext
from capabilities.manifest import discover_manifest_paths, load_manifest
from server.gateway.contract import result_to_v1


def _parse_params(pairs):
    params = {}
    for p in pairs or []:
        if '=' not in p:
            continue
        k, v = p.split('=', 1)
        k = k.strip()
        v = v.strip()
        if v.startswith('{') or v.startswith('['):
            try:
                v = json.loads(v)
            except json.JSONDecodeError:
                pass
        params[k] = v
    return params


def _build_body(args) -> dict:
    if not sys.stdin.isatty():
        raw = sys.stdin.read()
        if raw.strip():
            return json.loads(raw)
    params = _parse_params(getattr(args, 'param', None))
    return {
        'run_id': getattr(args, 'run_id', None) or 'cli',
        'step_id': getattr(args, 'step_id', None) or 'main',
        'params': params,
        'inputs': {},
    }


def _manifest_cli(tool_id: str) -> str | None:
    for path in discover_manifest_paths():
        try:
            data = load_manifest(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if data.get('id') == tool_id:
            cli = (data.get('entry') or {}).get('cli')
            return str(cli).strip() if cli else None
    return None


def cmd_tool_invoke(args) -> int:
    from capabilities.registry import init_registry

    body = _build_body(args)
    reg = init_registry()
    ctx = RunContext(
        run_id=body.get('run_id'),
        step_id=body.get('step_id'),
        params=body.get('params') or {},
        inputs=body.get('inputs') or {},
    )
    try:
        result = reg.execute(args.tool_id, ctx)
    except ValueError as exc:
        print(json.dumps({'status': 'failed', 'outputs': {}, 'artifacts': [], 'error': str(exc)}))
        return 1
    print(json.dumps(result_to_v1(result), ensure_ascii=False))
    return 0 if result.status in ('done', 'skipped', 'waiting_human') else 1


def cmd_tool_run(args) -> int:
    cli_cmd = _manifest_cli(args.tool_id)
    if not cli_cmd:
        print(f'工具 {args.tool_id} 未声明 entry.cli，请使用: iisp tool invoke {args.tool_id}', file=sys.stderr)
        return 1
    body = _build_body(args)
    parts = shlex.split(cli_cmd)
    from studio.paths import APP_ROOT
    env = os.environ.copy()
    root = str(APP_ROOT)
    env['PYTHONPATH'] = root if not env.get('PYTHONPATH') else f"{root}{os.pathsep}{env['PYTHONPATH']}"
    proc = subprocess.run(
        parts,
        input=json.dumps(body, ensure_ascii=False),
        capture_output=True,
        text=True,
        cwd=os.environ.get('IISP_CLI_CWD') or None,
        env=env,
    )
    if proc.stdout:
        sys.stdout.write(proc.stdout)
        if not proc.stdout.endswith('\n'):
            sys.stdout.write('\n')
    if proc.stderr:
        sys.stderr.write(proc.stderr)
    return proc.returncode
