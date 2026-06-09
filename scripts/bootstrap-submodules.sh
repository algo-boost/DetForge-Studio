#!/usr/bin/env bash
# IISP：初始化 packages/ 下 git submodule
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
echo "==> IISP submodule init ($ROOT)"
git submodule update --init --recursive
echo "==> packages:"
ls -la packages/ 2>/dev/null || true
echo "Done. Run: python app.py  # http://localhost:5050"
