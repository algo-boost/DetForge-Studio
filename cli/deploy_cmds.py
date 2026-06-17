"""iisp deploy 子命令实现。"""
from __future__ import annotations

import argparse
import os
import sys

from orchestration.native.defaults import load_defaults
from orchestration.native.process_manager import (
    DeployError,
    collect_status,
    require_config,
    start_iisp,
    stop_platform,
)
from studio.paths import APP_ROOT

IS_WINDOWS = os.name == 'nt'
STOP_HINT = (
    'powershell deploy\\scripts\\platform-stop.ps1'
    if IS_WINDOWS
    else 'bash deploy/scripts/platform-stop.sh'
)


def cmd_deploy_status(_args: argparse.Namespace) -> int:
    defaults = load_defaults()
    for row in collect_status(defaults):
        if row.running and row.http_ok:
            print(f"  {row.name}: running (pid {row.pid}) — {row.url}")
        elif row.running:
            print(f"  {row.name}: pid {row.pid} 但 HTTP 未响应")
        else:
            print(f"  {row.name}: stopped")
    return 0


def cmd_deploy_start(args: argparse.Namespace) -> int:
    try:
        return _deploy_start(args)
    except DeployError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


def _deploy_start(_args: argparse.Namespace) -> int:
    defaults = load_defaults()
    print('==> IISP 平台启动（原生）')
    print(f'    APP_ROOT={APP_ROOT}')
    require_config()

    print(f'==> 启动 IISP :{defaults.iisp_port}')
    iisp_pid = start_iisp(defaults=defaults)
    if iisp_pid:
        print(f'    OK IISP {defaults.iisp_url} (pid {iisp_pid})')

    print('')
    print('==========================================')
    print(f'  IISP   {defaults.iisp_url}/')
    print(f'  停止   {STOP_HINT}')
    print('==========================================')
    return 0


def cmd_deploy_stop(_args: argparse.Namespace) -> int:
    stop_platform()
    print('==> 平台已停止')
    return 0


def register_deploy_subparser(sub: argparse._SubParsersAction) -> None:
    deploy = sub.add_parser('deploy', help='原生 IISP 部署')
    deploy_sub = deploy.add_subparsers(dest='deploy_cmd')

    p_status = deploy_sub.add_parser('status', help='平台进程状态')
    p_status.set_defaults(func=cmd_deploy_status)

    p_start = deploy_sub.add_parser('start', help='启动 IISP')
    p_start.set_defaults(func=cmd_deploy_start)

    p_stop = deploy_sub.add_parser('stop', help='停止 IISP')
    p_stop.set_defaults(func=cmd_deploy_stop)
