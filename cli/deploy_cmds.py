"""iisp deploy 子命令实现。"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from orchestration.native.bootstrap import ensure_kestra_database
from orchestration.native.config_render import render_kestra_application
from orchestration.native.defaults import load_defaults
from orchestration.native.paths import DEPLOY_ROOT, KESTRA_BIN
from orchestration.native.process_manager import (
    DeployError,
    collect_status,
    require_config,
    require_java,
    start_iisp,
    start_kestra,
    stop_platform,
)
from studio.paths import APP_ROOT


def cmd_deploy_bootstrap_db(args: argparse.Namespace) -> int:
    db = ensure_kestra_database(args.database or None)
    print(f'OK database `{db}` ready')
    return 0


def cmd_deploy_render_config(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    out = render_kestra_application(
        deploy_root=Path(args.deploy_root) if args.deploy_root else None,
        defaults=defaults,
        kestra_database=args.database or None,
    )
    print(out)
    return 0


def cmd_deploy_status(_args: argparse.Namespace) -> int:
    defaults = load_defaults()
    for row in collect_status(defaults):
        if row.running and row.http_ok:
            print(f"  {row.name}: running (pid {row.pid}) — {row.url}")
        elif row.running:
            print(f"  {row.name}: pid {row.pid} 但 HTTP 未响应")
        else:
            print(f"  {row.name}: stopped")
    if KESTRA_BIN.is_file():
        print(f'  vendor: {KESTRA_BIN}')
    else:
        print('  vendor: 未下载（运行 fetch_kestra.sh 或 platform-start.sh）')
    return 0


def cmd_deploy_start(args: argparse.Namespace) -> int:
    try:
        return _deploy_start(args)
    except DeployError as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1


def _deploy_start(args: argparse.Namespace) -> int:
    defaults = load_defaults()
    print('==> IISP 平台启动（原生）')
    print(f'    APP_ROOT={APP_ROOT}')
    print(f'==> Java: {require_java()}')
    require_config()

    if not KESTRA_BIN.is_file():
        fetch = DEPLOY_ROOT / 'scripts' / 'fetch_kestra.sh'
        print('==> 首次运行：下载 Kestra…')
        subprocess.check_call(['bash', str(fetch)])

    print(f'==> Bootstrap MySQL 库 `{defaults.kestra_mysql_database}`')
    ensure_kestra_database(defaults.kestra_mysql_database)

    print('==> 渲染 Kestra 配置')
    config_yml = render_kestra_application(defaults=defaults, kestra_database=defaults.kestra_mysql_database)

    print(f'==> 启动 Kestra :{defaults.kestra_port}')
    kestra_pid = start_kestra(config_yml=config_yml, defaults=defaults)
    if kestra_pid:
        print(f'    OK Kestra UI {defaults.kestra_url} (pid {kestra_pid})')

    print(f'==> 启动 IISP :{defaults.iisp_port}')
    iisp_pid = start_iisp(defaults=defaults)
    if iisp_pid:
        print(f'    OK IISP {defaults.iisp_url} (pid {iisp_pid})')

    print('')
    print('==========================================')
    print(f'  IISP   {defaults.iisp_url}/')
    print(f'  Kestra {defaults.kestra_url}/  ({defaults.kestra_user})')
    print('  停止   bash deploy/scripts/platform-stop.sh')
    print('==========================================')
    return 0


def cmd_deploy_stop(_args: argparse.Namespace) -> int:
    stop_platform()
    print('==> 平台已停止')
    return 0


def register_deploy_subparser(sub: argparse._SubParsersAction) -> None:
    deploy = sub.add_parser('deploy', help='原生一体部署（Kestra + IISP）')
    deploy_sub = deploy.add_subparsers(dest='deploy_cmd')

    p_boot = deploy_sub.add_parser('bootstrap-db', help='创建 Kestra MySQL 库')
    p_boot.add_argument('--database', default='')
    p_boot.set_defaults(func=cmd_deploy_bootstrap_db)

    p_render = deploy_sub.add_parser('render-config', help='渲染 kestra-application.yml')
    p_render.add_argument('--deploy-root', default='')
    p_render.add_argument('--database', default='')
    p_render.set_defaults(func=cmd_deploy_render_config)

    p_status = deploy_sub.add_parser('status', help='平台进程状态')
    p_status.set_defaults(func=cmd_deploy_status)

    p_start = deploy_sub.add_parser('start', help='启动 Kestra + IISP')
    p_start.set_defaults(func=cmd_deploy_start)

    p_stop = deploy_sub.add_parser('stop', help='停止 Kestra + IISP')
    p_stop.set_defaults(func=cmd_deploy_stop)
