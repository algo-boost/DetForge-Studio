#!/usr/bin/env bash
# 下载 Kestra 可执行文件 + 插件到 deploy/vendor/（打包时执行一次）
set -euo pipefail

DEPLOY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
# shellcheck source=/dev/null
source "$DEPLOY_ROOT/native/env.defaults"

VENDOR="$DEPLOY_ROOT/vendor"
KESTRA_BIN="$VENDOR/kestra"
PLUGINS_DIR="$VENDOR/plugins"
IMAGE="kestra/kestra:${KESTRA_VERSION}"

mkdir -p "$VENDOR"

if [[ -x "$KESTRA_BIN" && -d "$PLUGINS_DIR" ]]; then
  echo "==> Kestra 已存在: $KESTRA_BIN"
  exit 0
fi

echo "==> 获取 Kestra ${KESTRA_VERSION} → $VENDOR"

if command -v docker >/dev/null 2>&1; then
  echo "    从 Docker 镜像提取（含插件）: $IMAGE"
  cid="$(docker create "$IMAGE")"
  trap 'docker rm -f "$cid" >/dev/null 2>&1 || true' EXIT
  docker cp "$cid:/app/kestra" "$KESTRA_BIN"
  docker cp "$cid:/app/plugins" "$PLUGINS_DIR"
  docker rm -f "$cid"
  trap - EXIT
  chmod +x "$KESTRA_BIN"
  echo "    OK docker extract"
  exit 0
fi

echo "    Docker 不可用，尝试 Kestra API 下载…"
TMP="$VENDOR/.download"
mkdir -p "$TMP"
curl -fsSL "https://api.kestra.io/v1/releases/${KESTRA_VERSION}/download/kestra" -o "$TMP/kestra"
chmod +x "$TMP/kestra"
mv "$TMP/kestra" "$KESTRA_BIN"

mkdir -p "$PLUGINS_DIR"
echo "    安装 core 插件（HTTP / Flow 等）…"
"$KESTRA_BIN" plugins install "$PLUGINS_DIR" io.kestra.plugin.core || {
  echo "警告: 插件安装失败，Flow 可能无法运行。建议在有 Docker 的环境重新执行 fetch_kestra.sh" >&2
}

echo "    OK api download"
