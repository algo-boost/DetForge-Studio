"""iisp agent 子命令（任意 IDE Agent 自举）。"""
from __future__ import annotations

import argparse
import json


def cmd_agent_context(args: argparse.Namespace) -> int:
    from orchestration.agent_context import build_agent_context

    ctx = build_agent_context()
    print(json.dumps(ctx, ensure_ascii=False, indent=2 if args.pretty else None))
    return 0


def register_agent_subparser(sub: argparse._SubParsersAction) -> None:
    agent = sub.add_parser('agent', help='Agent 自举（IDE 无关）')
    agent_sub = agent.add_subparsers(dest='agent_cmd')

    p_ctx = agent_sub.add_parser('context', help='输出 Skills/Rules/CLI 索引 JSON')
    p_ctx.add_argument('--json', action='store_true', help='JSON 输出（默认）')
    p_ctx.add_argument('--pretty', action='store_true', default=True)
    p_ctx.set_defaults(func=cmd_agent_context)
