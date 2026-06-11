#!/usr/bin/env bash
# Query 工具独立部署：UI + REST + Gateway invoke（默认 :6021）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

if [[ "${SKIP_QUERY_UI_BUILD:-0}" != "1" ]]; then
  bash tools/query/ui/build.sh
fi

export QUERY_TOOL_PORT="${QUERY_TOOL_PORT:-6021}"
echo "==> Query standalone http://127.0.0.1:${QUERY_TOOL_PORT}/"
exec python3 -m tools.query.standalone
