#!/usr/bin/env bash
# DefectLoop Studio 本地开发：构建前端 + 启动 Flask + Worker
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

build_frontend() {
  if [[ "${SKIP_FRONTEND_BUILD:-0}" != "1" ]]; then
    echo "==> building frontend..."
    (cd frontend && npm run build)
  fi
}

start_worker() {
  if [[ "${PC_NO_WORKER:-0}" == "1" ]]; then
    echo "==> worker disabled (PC_NO_WORKER=1)"
    return
  fi
  echo "==> starting worker..."
  python worker.py &
  WORKER_PID=$!
  trap 'kill "$WORKER_PID" 2>/dev/null || true' EXIT
}

main() {
  build_frontend
  start_worker
  echo "==> starting Flask on http://127.0.0.1:5050"
  exec python app.py
}

main "$@"
