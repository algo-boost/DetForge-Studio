#!/usr/bin/env python3
"""兼容入口：iisp deploy bootstrap-db"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli.deploy_cmds import cmd_deploy_bootstrap_db  # noqa: E402
import argparse  # noqa: E402

if __name__ == '__main__':
    ns = argparse.Namespace(database='')
    if len(sys.argv) > 1 and sys.argv[1] == '--database' and len(sys.argv) > 2:
        ns.database = sys.argv[2]
    raise SystemExit(cmd_deploy_bootstrap_db(ns))
