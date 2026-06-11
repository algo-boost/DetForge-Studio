#!/usr/bin/env bash
# 编排闭环演示 — 样本模式全自动 / 真实库 UI 触发
#
# 用法:
#   bash scripts/run-closed-loop-demo.sh              # 样本数据，Pause 后自动回传 COCO → SUCCESS
#   bash scripts/run-closed-loop-demo.sh --real --ui  # 仅触发真实库 Flow，手动在 /curation Resume
#   bash scripts/run-closed-loop-demo.sh --help
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MODE="smoke"
UI_ONLY=0

usage() {
  cat <<'EOF'
编排闭环演示

  bash scripts/run-closed-loop-demo.sh
      样本模式（closed_loop_demo_smoke），无需业务库，全自动跑通到 SUCCESS

  bash scripts/run-closed-loop-demo.sh --real --ui
      真实库查询（closed_loop_demo），仅触发 Flow，在 Shell /flows 或 /curation 人工 Resume

环境: IISP :5050、Kestra :8080 已启动（platform-start.sh）
EOF
}

for arg in "$@"; do
  case "$arg" in
    --real) MODE="real" ;;
    --ui|--ui-only) UI_ONLY=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "未知参数: $arg" >&2; usage; exit 1 ;;
  esac
done

IISP_URL="${IISP_URL:-http://127.0.0.1:5050}"

if [ "$MODE" = "real" ]; then
  FLOW_ID="closed_loop_demo"
else
  FLOW_ID="closed_loop_demo_smoke"
fi

echo "==> 初始化 forge schema（如需）"
curl -sf "$IISP_URL/v1/tools" >/dev/null
curl -s -o /dev/null -w "schema/init HTTP=%{http_code}\n" -X POST "$IISP_URL/api/forge/schema/init" || true

if [ "$UI_ONLY" = 1 ]; then
  echo "==> 触发 Flow（UI 模式）: $FLOW_ID"
  RESP=$(curl -sf -X POST "$IISP_URL/api/flows/kestra/execute" \
    -H 'Content-Type: application/json' \
    -d "{\"flow_id\":\"$FLOW_ID\",\"inputs\":{}}")
  echo "$RESP" | python3 -m json.tool
  RUN_KEY=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('run_key',''))")
  KURL=$(echo "$RESP" | python3 -c "import json,sys; print(json.load(sys.stdin).get('data',{}).get('kestra_url',''))")
  echo ""
  echo "Shell 运行详情: $IISP_URL/flows/runs/${RUN_KEY}"
  [ -n "$KURL" ] && echo "Kestra UI: $KURL"
  echo ""
  echo "Pause 后请到「筛选归档」处理 COCO，再在 /flows/runs 点 Resume。"
  exit 0
fi

echo "==> 全自动闭环 flow=${FLOW_ID}"
FLOW_ID="${FLOW_ID}" FLOW_FILE="${ROOT}/iisp-catalog/pipelines/kestra/${FLOW_ID}.yaml" \
  exec bash "${ROOT}/deploy/scripts/daily_ng_pause_resume_e2e.sh"
