"""iisp flow 子命令：Kestra 执行、状态、Resume、Shell 导出。"""
from __future__ import annotations

import argparse
import json
import sys


def parse_flow_params(pairs: list[str] | None) -> dict:
    params: dict = {}
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


def cmd_flow_execute(args: argparse.Namespace) -> int:
    from server.services.flows import execute_kestra_flow

    inputs = parse_flow_params(args.param)
    try:
        result = execute_kestra_flow(
            args.flow_id,
            namespace=args.namespace or None,
            inputs=inputs or None,
        )
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if result.get('status') == 'waiting_human':
        print('\n⏸  流程已 PAUSED。恢复: iisp flow resume <run_key>', file=sys.stderr)
        return 2
    return 0


def cmd_flow_status(args: argparse.Namespace) -> int:
    from server.services.flows import get_flow_run

    run = get_flow_run(args.run_key)
    if not run:
        print(f'运行记录未找到: {args.run_key}', file=sys.stderr)
        return 1
    print(json.dumps(run, ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_flow_resume(args: argparse.Namespace) -> int:
    from server.services.flows import resume_flow_run

    body: dict = {}
    if args.approved_by:
        body['approved_by'] = args.approved_by
    inputs = parse_flow_params(args.param)
    if inputs:
        body['inputs'] = inputs
    try:
        result = resume_flow_run(args.run_key, body)
    except (ValueError, RuntimeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_flow_export_shell(args: argparse.Namespace) -> int:
    from orchestration.flow_shell_export import export_kestra_flow_shell

    try:
        script = export_kestra_flow_shell(args.flow_id)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as f:
            f.write(script)
        print(f'已写入: {args.out}')
    else:
        print(script, end='')
    return 0


def register_flow_subparser(sub: argparse._SubParsersAction) -> None:
    flow = sub.add_parser('flow', help='编排 Flow（本地 / Kestra / Shell 导出）')
    flow_sub = flow.add_subparsers(dest='flow_cmd')

    p_flist = flow_sub.add_parser('list', help='列出 Catalog Pipeline')
    p_flist.set_defaults(func=_cmd_flow_list)

    p_fklist = flow_sub.add_parser('list-kestra', help='列出 Kestra Flow YAML')
    p_fklist.set_defaults(func=_cmd_flow_list_kestra)

    p_frun = flow_sub.add_parser('run', help='运行 Legacy Pipeline YAML 或 flow id')
    p_frun.add_argument('flow', help='YAML 路径或 flow id')
    p_frun.add_argument('--param', action='append', help='参数 key=value')
    p_frun.add_argument('--reviewer', default='', help='快捷设置 params.reviewer')
    p_frun.add_argument('--auto-resume', action='store_true', help='自动跳过 gate-human')
    p_frun.set_defaults(func=_cmd_flow_run)

    p_fexec = flow_sub.add_parser('execute', help='触发 Kestra Flow 执行')
    p_fexec.add_argument('flow_id', help='Kestra flow id，如 daily_ng_curation_smoke')
    p_fexec.add_argument('--param', action='append', help='inputs key=value，可重复')
    p_fexec.add_argument('--namespace', default='', help='Kestra namespace，默认 iisp')
    p_fexec.set_defaults(func=cmd_flow_execute)

    p_fstatus = flow_sub.add_parser('status', help='查询运行记录（run_key）')
    p_fstatus.add_argument('run_key', help='如 kestra:ex-xxx 或 demo:...')
    p_fstatus.set_defaults(func=cmd_flow_status)

    p_fresume = flow_sub.add_parser('resume', help='恢复 PAUSED 运行')
    p_fresume.add_argument('run_key', help='kestra:execution_id 等')
    p_fresume.add_argument('--approved-by', default='', help='demo/workflow 恢复审批人')
    p_fresume.add_argument('--param', action='append', help='resume inputs key=value')
    p_fresume.set_defaults(func=cmd_flow_resume)

    p_fexport = flow_sub.add_parser('export-shell', help='导出 dev shell 工具链')
    p_fexport.add_argument('flow_id', help='Kestra flow id')
    p_fexport.add_argument('-o', '--out', default='', help='写入文件路径')
    p_fexport.set_defaults(func=cmd_flow_export_shell)


def _cmd_flow_list(args: argparse.Namespace) -> int:
    from orchestration.loader import discover_pipelines

    for p in discover_pipelines():
        flag = 'ok' if p.get('_valid') else 'bad'
        path = p.get('_path') or '-'
        print(f"{p.get('id') or '?'}\t{flag}\t{p.get('name') or ''}\t{path}")
    return 0


def _cmd_flow_list_kestra(args: argparse.Namespace) -> int:
    from orchestration.loader import discover_kestra_flows

    for f in discover_kestra_flows():
        flag = 'ok' if f.get('_valid') else 'bad'
        print(
            f"{f.get('namespace')}.{f.get('id')}\t{flag}\t"
            f"{f.get('description') or ''}\t{f.get('_path')}"
        )
    return 0


def _cmd_flow_run(args: argparse.Namespace) -> int:
    from orchestration.flow_runner import find_pipeline, run_flow

    try:
        defn, _path = find_pipeline(args.flow)
    except FileNotFoundError as exc:
        print(str(exc))
        return 1
    params = parse_flow_params(args.param)
    if args.reviewer and 'reviewer' not in params:
        params['reviewer'] = args.reviewer
    result = run_flow(defn, params, auto_resume=args.auto_resume)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.status == 'waiting_human':
        print('\n⏸  流程在人工卡点暂停。加 --auto-resume 可自动跳过。')
        return 2
    return 0 if result.status == 'done' else 1
