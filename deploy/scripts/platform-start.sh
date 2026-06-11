#!/usr/bin/env bash
# 薄入口 → orchestration.native + iisp deploy
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec python3 -m cli.main deploy start "$@"
