#!/usr/bin/env python3
"""兼容入口：iisp deploy render-config"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli.main import main  # noqa: E402

if __name__ == '__main__':
    argv = ['deploy', 'render-config']
    if '--deploy-root' in sys.argv:
        i = sys.argv.index('--deploy-root')
        argv.extend(['--deploy-root', sys.argv[i + 1]])
    raise SystemExit(main(argv))
