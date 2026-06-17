"""iisp flow 子命令：Legacy Pipeline 运行、状态、Resume。"""
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


def register_flow_subparser(sub: argparse._SubParsersAction) -> None:
    flow = sub.add_parser('flow', help='编排 Flow（Legacy Pipeline / 组合编排 run_key）')
    flow_sub = flow.add_subparsers(dest='flow_cmd')

    p_flist = flow_sub.add_parser('list', help='列出 Catalog Pipeline')
    p_flist.set_defaults(func=_cmd_flow_list)

    p_frun = flow_sub.add_parser('run', help='运行 Legacy Pipeline YAML 或 flow id')
    p_frun.add_argument('flow', help='YAML 路径或 flow id')
    p_frun.add_argument('--param', action='append', help='参数 key=value')
    p_frun.add_argument('--reviewer', default='', help='快捷设置 params.reviewer')
    p_frun.add_argument('--auto-resume', action='store_true', help='自动跳过 gate-human')
    p_frun.set_defaults(func=_cmd_flow_run)

    p_fstatus = flow_sub.add_parser('status', help='查询运行记录（run_key）')
    p_fstatus.add_argument('run_key', help='如 workflow:9 或 demo:...')
    p_fstatus.set_defaults(func=cmd_flow_status)

    p_fresume = flow_sub.add_parser('resume', help='恢复 PAUSED 运行')
    p_fresume.add_argument('run_key', help='workflow:run_id 或 demo:run_id')
    p_fresume.add_argument('--approved-by', default='', help='demo/workflow 恢复审批人')
    p_fresume.add_argument('--param', action='append', help='resume inputs key=value')
    p_fresume.set_defaults(func=cmd_flow_resume)


def _cmd_flow_list(args: argparse.Namespace) -> int:
    from orchestration.loader import discover_pipelines

    for p in discover_pipelines():
        flag = 'ok' if p.get('_valid') else 'bad'
        path = p.get('_path') or '-'
        print(f"{p.get('id') or '?'}\t{flag}\t{p.get('name') or ''}\t{path}")
    return 0


def _cmd_flow_run(args: argparse.Namespace) -> int:
    from orchestration.flow_runner import find_pipeline, run_flow

    params = parse_flow_params(args.param)
    if args.reviewer:
        params['reviewer'] = args.reviewer
    defn, path = find_pipeline(args.flow)
    result = run_flow(defn, params, auto_resume=args.auto_resume)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == 'done' else 2
