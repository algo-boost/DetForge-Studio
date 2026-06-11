#!/usr/bin/env bash
# 打包 IISP + Kestra 为可分发的 tar.gz（含 vendor/ 二进制）
set -euo pipefail

DEPLOY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_ROOT="$(cd "$DEPLOY_ROOT/.." && pwd)"
# shellcheck source=/dev/null
source "$DEPLOY_ROOT/native/env.defaults"

OUT_DIR="${1:-$APP_ROOT/packaging/dist}"
STAMP="$(date +%Y%m%d)"
NAME="iisp-platform-${KESTRA_VERSION}-${STAMP}"
STAGE="$OUT_DIR/.pack-staging/$NAME"

echo "==> 预取 Kestra ${KESTRA_VERSION}"
bash "$DEPLOY_ROOT/scripts/fetch_kestra.sh"

echo "==>  staging → $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE"

rsync -a \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude 'venv' \
  --exclude 'node_modules' \
  --exclude 'frontend/node_modules' \
  --exclude 'frontend/dist' \
  --exclude 'datasets' \
  --exclude 'uploads' \
  --exclude 'exports' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude 'config.json' \
  --exclude '.config.key' \
  --exclude 'packaging/dist' \
  --exclude 'deploy/runtime' \
  "$APP_ROOT/" "$STAGE/"

mkdir -p "$OUT_DIR"
ARCHIVE="$OUT_DIR/${NAME}.tar.gz"
tar -czf "$ARCHIVE" -C "$OUT_DIR/.pack-staging" "$NAME"
rm -rf "$OUT_DIR/.pack-staging"

BYTES="$(wc -c <"$ARCHIVE" | tr -d ' ')"
echo ""
echo "=========================================="
echo "  打包完成: $ARCHIVE"
echo "  大小: $(( BYTES / 1024 / 1024 )) MB"
echo ""
echo "  目标机解压后:"
echo "    1. 配置 config.json + .config.key"
echo "    2. pip install -r requirements.txt && cd frontend && npm ci && npm run build"
echo "    3. bash deploy/scripts/platform-start.sh"
echo "=========================================="
