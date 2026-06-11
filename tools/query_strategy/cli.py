"""兼容入口 — 转发至 query.cli。"""
from __future__ import annotations

import sys

from tools.query.cli import main

if __name__ == '__main__':
    main(sys.argv[1:])
