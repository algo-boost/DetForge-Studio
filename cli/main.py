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

from cli.deploy_cmds import register_deploy_subparser  # noqa: E402
from cli.agent_cmds import register_agent_subparser  # noqa: E402
from cli.flow_cmds import register_flow_subparser  # noqa: E402


def cmd_catalog_sync(args):
    from orchestration.catalog_sync import sync_catalog
    result = sync_catalog(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get('success') else 1


def cmd_workflow_validate(args):
    from orchestration.loader import load_pipeline_yaml
    from orchestration.pipeline_validate import validate_pipeline_any
    defn = load_pipeline_yaml(args.path)
    errors = validate_pipeline_any(defn, path=args.path)
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


def cmd_tool_invoke(args):
    from cli.tool_invoke import cmd_tool_invoke as _invoke
    return _invoke(args)


def cmd_tool_run(args):
    from cli.tool_invoke import cmd_tool_run as _run
    return _run(args)


def cmd_skill_validate(args):
    from cli.skill_pack import validate_skill
    out = validate_skill(args.skill_path)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('success') else 1


def cmd_skill_pack(args):
    from cli.skill_pack import pack_skill, validate_skill
    check = validate_skill(args.skill_path)
    tool_id = check.get('name') or 'tool'
    out_dir = args.out or str(_ROOT / 'tools' / tool_id)
    out = pack_skill(args.skill_path, out_dir, install=args.install)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get('success') else 1


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
    p_tinv = tool_sub.add_parser('invoke', help='in-process 调用工具（stdin JSON 或 --param）')
    p_tinv.add_argument('tool_id')
    p_tinv.add_argument('--param', action='append', help='params.key=value，可重复')
    p_tinv.add_argument('--run-id', default='cli')
    p_tinv.add_argument('--step-id', default='main')
    p_tinv.set_defaults(func=cmd_tool_invoke)
    p_trun = tool_sub.add_parser('run', help='子进程 CLI 调用（Manifest entry.cli）')
    p_trun.add_argument('tool_id')
    p_trun.add_argument('--param', action='append', help='params.key=value，可重复')
    p_trun.add_argument('--run-id', default='cli')
    p_trun.add_argument('--step-id', default='main')
    p_trun.set_defaults(func=cmd_tool_run)

    p_skill = sub.add_parser('skill', help='Platform Skill 校验与封装')
    skill_sub = p_skill.add_subparsers(dest='skill_cmd')
    p_sval = skill_sub.add_parser('validate', help='校验 SKILL.md')
    p_sval.add_argument('skill_path')
    p_sval.set_defaults(func=cmd_skill_validate)
    p_spack = skill_sub.add_parser('pack', help='SKILL → Tool 包（validate + init + manifest v1）')
    p_spack.add_argument('skill_path')
    p_spack.add_argument('--out', default='', help='输出目录，默认 tools/<name>/')
    p_spack.add_argument('--install', action='store_true', help='pack 后 reload Registry')
    p_spack.set_defaults(func=cmd_skill_pack)

    register_flow_subparser(sub)

    register_deploy_subparser(sub)
    register_agent_subparser(sub)

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
    if args.command == 'tool' and args.tool_cmd == 'invoke':
        return cmd_tool_invoke(args)
    if args.command == 'tool' and args.tool_cmd == 'run':
        return cmd_tool_run(args)
    if args.command == 'skill' and args.skill_cmd == 'validate':
        return cmd_skill_validate(args)
    if args.command == 'skill' and args.skill_cmd == 'pack':
        return cmd_skill_pack(args)
    if args.command == 'flow' and getattr(args, 'func', None):
        return args.func(args)
    if args.command == 'deploy' and getattr(args, 'func', None):
        return args.func(args)
    if args.command == 'agent' and getattr(args, 'func', None):
        return args.func(args)
    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
