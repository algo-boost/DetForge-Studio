#!/usr/bin/env python3
"""IISP CLI: catalog sync | workflow validate | tool validate/list | tool init-from-skill."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保主仓在 path
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def cmd_catalog_sync(args):
    from orchestration.catalog_sync import sync_catalog
    result = sync_catalog(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('success') else 1


def cmd_workflow_validate(args):
    from orchestration.loader import load_pipeline_yaml, validate_pipeline
    defn = load_pipeline_yaml(args.path)
    errors = validate_pipeline(defn)
    if errors:
        print('校验失败:')
        for e in errors:
            print(f'  - {e}')
        return 1
    print('校验通过:', defn.get('id'))
    return 0


def cmd_workflow_apply(args):
    from orchestration.loader import load_pipeline_yaml, pipeline_to_workflow_definition, validate_pipeline
    from studio.forge import forge_db

    defn = load_pipeline_yaml(args.path)
    errors = validate_pipeline(defn)
    if errors:
        print('校验失败:', errors)
        return 1
    if args.dry_run:
        print(json.dumps(pipeline_to_workflow_definition(defn), ensure_ascii=False, indent=2))
        return 0
    tpl = {
        'id': defn['id'],
        'name': defn.get('name') or defn['id'],
        'description': defn.get('description') or '',
        'version': int(defn.get('version') or 1),
        'builtin': 0,
        'definition': pipeline_to_workflow_definition(defn),
    }
    forge_db.upsert_workflow_template(tpl)
    print(f'已写入工作流模板: {tpl["id"]}')
    return 0


def cmd_tool_validate(args):
    from capabilities.manifest import load_manifest, validate_manifest
    paths = args.paths or []
    if not paths:
        from capabilities.manifest import discover_manifest_paths
        paths = discover_manifest_paths()
    ok = True
    for p in paths:
        data = load_manifest(p)
        errs = validate_manifest(data, path=p)
        if errs:
            ok = False
            print(f'FAIL {p}:')
            for e in errs:
                print(f'  - {e}')
        else:
            print(f'OK   {p}')
    return 0 if ok else 1


def cmd_tool_list(args):
    from capabilities.registry import init_registry
    reg = init_registry()
    for t in reg.list_tools():
        print(f"{t['id']}\t{t.get('version') or '-'}\t{t['kind']}\t{t['label']}")
    return 0


def cmd_tool_init_from_skill(args):
    from cli.tool_init import init_tool_from_skill
    out = init_tool_from_skill(args.skill_path, args.out)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('success') else 1


def _parse_flow_params(pairs):
    params = {}
    for p in pairs or []:
        if '=' not in p:
            continue
        k, v = p.split('=', 1)
        params[k.strip()] = v.strip()
    return params


def cmd_flow_list(args):
    from orchestration.loader import discover_pipelines
    for p in discover_pipelines():
        flag = 'ok' if p.get('_valid') else 'bad'
        path = p.get('_path') or '-'
        print(f"{p.get('id') or '?'}\t{flag}\t{p.get('name') or ''}\t{path}")
    return 0


def cmd_flow_run(args):
    from orchestration.flow_runner import find_pipeline, run_flow

    try:
        defn, path = find_pipeline(args.flow)
    except FileNotFoundError as e:
        print(str(e))
        return 1
    params = _parse_flow_params(args.param)
    if args.reviewer and 'reviewer' not in params:
        params['reviewer'] = args.reviewer
    result = run_flow(defn, params, auto_resume=args.auto_resume)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    if result.status == 'waiting_human':
        print('\n⏸  流程在人工卡点暂停。加 --auto-resume 可自动跳过，或在 Web /demo 页点击继续。')
        return 2
    return 0 if result.status == 'done' else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog='iisp', description='IISP 工具箱与编排 CLI')
    sub = parser.add_subparsers(dest='command')

    p_cat = sub.add_parser('catalog', help='Catalog 配置同步')
    cat_sub = p_cat.add_subparsers(dest='catalog_cmd')
    p_sync = cat_sub.add_parser('sync', help='从 Git Catalog 同步')
    p_sync.add_argument('--dry-run', action='store_true')
    p_sync.set_defaults(func=cmd_catalog_sync)

    p_wf = sub.add_parser('workflow', help='工作流 Pipeline')
    wf_sub = p_wf.add_subparsers(dest='workflow_cmd')
    p_val = wf_sub.add_parser('validate', help='校验 Pipeline YAML')
    p_val.add_argument('path')
    p_val.set_defaults(func=cmd_workflow_validate)
    p_apply = wf_sub.add_parser('apply', help='导入 Pipeline 为工作流模板')
    p_apply.add_argument('path')
    p_apply.add_argument('--dry-run', action='store_true')
    p_apply.set_defaults(func=cmd_workflow_apply)

    p_tool = sub.add_parser('tool', help='工具箱')
    tool_sub = p_tool.add_subparsers(dest='tool_cmd')
    p_tval = tool_sub.add_parser('validate', help='校验 tool.manifest.json')
    p_tval.add_argument('paths', nargs='*')
    p_tval.set_defaults(func=cmd_tool_validate)
    p_tlist = tool_sub.add_parser('list', help='列出已注册工具')
    p_tlist.set_defaults(func=cmd_tool_list)
    p_tinit = tool_sub.add_parser('init-from-skill', help='从 SKILL.md 生成工具包骨架')
    p_tinit.add_argument('skill_path')
    p_tinit.add_argument('--out', required=True)
    p_tinit.set_defaults(func=cmd_tool_init_from_skill)

    p_flow = sub.add_parser('flow', help='本地 Flow 运行（体验编排）')
    flow_sub = p_flow.add_subparsers(dest='flow_cmd')
    p_flist = flow_sub.add_parser('list', help='列出 Catalog Pipeline')
    p_flist.set_defaults(func=cmd_flow_list)
    p_frun = flow_sub.add_parser('run', help='运行 Pipeline YAML 或 flow id')
    p_frun.add_argument('flow', help='YAML 路径或 flow id（如 welcome_demo）')
    p_frun.add_argument('--param', action='append', help='参数 key=value，可重复')
    p_frun.add_argument('--reviewer', default='', help='快捷设置 params.reviewer')
    p_frun.add_argument('--auto-resume', action='store_true', help='自动跳过 gate-human 卡点')
    p_frun.set_defaults(func=cmd_flow_run)

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 1
    if args.command == 'catalog' and args.catalog_cmd == 'sync':
        return cmd_catalog_sync(args)
    if args.command == 'workflow' and args.workflow_cmd == 'validate':
        return cmd_workflow_validate(args)
    if args.command == 'workflow' and args.workflow_cmd == 'apply':
        return cmd_workflow_apply(args)
    if args.command == 'tool' and args.tool_cmd == 'validate':
        return cmd_tool_validate(args)
    if args.command == 'tool' and args.tool_cmd == 'list':
        return cmd_tool_list(args)
    if args.command == 'tool' and args.tool_cmd == 'init-from-skill':
        return cmd_tool_init_from_skill(args)
    if args.command == 'flow' and args.flow_cmd == 'list':
        return cmd_flow_list(args)
    if args.command == 'flow' and args.flow_cmd == 'run':
        return cmd_flow_run(args)
    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
