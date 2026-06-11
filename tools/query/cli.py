"""CLI：stdin JSON 或子命令。"""
from __future__ import annotations

import json
import sys

from lib.iisp_cli.contract import read_payload, run_capability_main, write_result
from tools.query.capability import QueryCapability


def _params_from_argv(argv: list[str]) -> dict:
    if not argv:
        return {}
    action = argv[0].strip().lower()
    params: dict = {'action': action}
    i = 1
    while i < len(argv):
        tok = argv[i]
        if tok.startswith('--'):
            key = tok[2:].replace('-', '_')
            if i + 1 < len(argv) and not argv[i + 1].startswith('--'):
                val = argv[i + 1]
                if val.startswith('{') or val.startswith('['):
                    try:
                        val = json.loads(val)
                    except json.JSONDecodeError:
                        pass
                params[key] = val
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1
    # 子命令简写：query-cli strategy list
    if action == 'strategy' and argv[1:2]:
        sub = argv[1].strip().lower()
        params = {'action': f'strategy.{sub}'}
        i = 2
        while i < len(argv):
            tok = argv[i]
            if tok.startswith('--'):
                key = tok[2:].replace('-', '_')
                if i + 1 < len(argv):
                    params[key] = argv[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
    elif action == 'execute' and 'strategy_id' not in params:
        for j, tok in enumerate(argv[1:], start=1):
            if tok == '--strategy' or tok == '--strategy-id':
                if j < len(argv):
                    params['strategy_id'] = argv[j]
    return params


def main(argv: list[str] | None = None) -> None:
    args = list(argv if argv is not None else sys.argv[1:])
    if args and not sys.stdin.isatty():
        run_capability_main(QueryCapability)
        return
    if args:
        payload = {'params': _params_from_argv(args), 'run_id': 'cli', 'step_id': 'main', 'inputs': {}}
        ctx_params = payload['params']
        cap = QueryCapability()
        from capabilities.base import RunContext
        result = cap.execute(RunContext(
            run_id='cli', step_id='main', params=ctx_params, inputs={},
        ))
        raise SystemExit(write_result(result))
    payload = read_payload()
    if payload:
        cap = QueryCapability()
        from capabilities.base import RunContext
        result = cap.execute(RunContext(
            run_id=payload.get('run_id'),
            step_id=payload.get('step_id'),
            params=payload.get('params') or {},
            inputs=payload.get('inputs') or {},
        ))
        raise SystemExit(write_result(result))
    print('用法: echo \'{"params":{"action":"strategy.list"}}\' | python3 -m tools.query.cli', file=sys.stderr)
    print('  或: python3 -m tools.query.cli strategy list', file=sys.stderr)
    print('  或: python3 -m tools.query.cli execute --strategy-id daily_trawl', file=sys.stderr)
    raise SystemExit(2)


if __name__ == '__main__':
    main()
