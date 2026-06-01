#!/usr/bin/env bash
# Playwright E2E：构建前端并启动 Flask（无 worker）
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
export PC_NO_WORKER=1
export PC_E2E=1
export E2E_PORT="${E2E_PORT:-5051}"
if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
  (cd frontend && npm run build)
fi
exec python -c "
from server.factory import create_app
app = create_app()
app.run(debug=False, host='127.0.0.1', port=int('${E2E_PORT}'), use_reloader=False)
"

