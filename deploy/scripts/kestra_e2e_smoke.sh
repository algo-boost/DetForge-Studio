#!/usr/bin/env bash
# 导入 daily_ng_curation Flow 并触发一次执行（M2 端到端冒烟）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FLOW_FILE="$ROOT/iisp-catalog/pipelines/kestra/daily_ng_curation.yaml"
KESTRA_URL="${KESTRA_URL:-http://127.0.0.1:8080}"
KESTRA_USER="${KESTRA_USER:-admin@kestra.io}"
KESTRA_PASSWORD="${KESTRA_PASSWORD:-Admin1234}"
IISP_URL="${IISP_URL:-http://127.0.0.1:5050}"
NS="iisp"
FLOW_ID="daily_ng_curation"
AUTH=(-u "$KESTRA_USER:$KESTRA_PASSWORD")
API="$KESTRA_URL/api/v1/main"

echo "==> IISP Gateway"
curl -sf "$IISP_URL/v1/tools" >/dev/null
echo "    OK $IISP_URL/v1/tools"

echo "==> Kestra health"
for i in $(seq 1 30); do
  if curl -sf "${AUTH[@]}" "$KESTRA_URL/" >/dev/null 2>&1; then
    echo "    OK $KESTRA_URL (auth: $KESTRA_USER)"
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    echo "Kestra 未就绪: $KESTRA_URL" >&2
    exit 1
  fi
done

echo "==> 导入 Flow (PUT $API/flows/$NS/$FLOW_ID)"
HTTP=$(curl -s -w '%{http_code}' -o /tmp/kestra_flow_resp.json "${AUTH[@]}" -X PUT "$API/flows/$NS/$FLOW_ID" \
  -H "Content-Type: application/x-yaml" \
  --data-binary @"$FLOW_FILE")
if [ "$HTTP" != "200" ]; then
  echo "    导入失败 HTTP=$HTTP" >&2
  cat /tmp/kestra_flow_resp.json >&2
  exit 1
fi
echo "    OK $NS/$FLOW_ID"

echo "==> 触发执行"
EXEC_JSON=$(curl -sf "${AUTH[@]}" -X POST "$API/executions/$NS/$FLOW_ID")
EXEC_ID=$(python3 -c "import json,sys; print(json.load(sys.stdin)['id'])" <<<"$EXEC_JSON")
echo "    execution_id=$EXEC_ID"
echo "$EXEC_JSON" | python3 -m json.tool | head -20

echo "==> 轮询状态（最多 120s）"
FINAL_STATE=""
for i in $(seq 1 24); do
  STATE=$(curl -sf "${AUTH[@]}" "$API/executions/$EXEC_ID" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('state',{}).get('current','?'))")
  echo "    [$i] state=$STATE"
  FINAL_STATE="$STATE"
  case "$STATE" in
    SUCCESS|FAILED|KILLED|CANCELLED) break ;;
    PAUSED) echo "    人工卡点 Pause — 请在 Kestra UI Resume: $KESTRA_URL/ui/main/executions/$NS/$FLOW_ID/$EXEC_ID"; break ;;
  esac
  sleep 5
done

if [ "$FINAL_STATE" = "SUCCESS" ]; then
  echo "==> 编排冒烟通过 (state=SUCCESS)"
elif [ "$FINAL_STATE" = "PAUSED" ]; then
  echo "==> 已到达人工卡点 (state=PAUSED)"
else
  echo "==> 执行未成功: state=$FINAL_STATE" >&2
  curl -sf "${AUTH[@]}" "$API/logs/$EXEC_ID" | python3 -c "
import json,sys
for x in json.load(sys.stdin):
    if x.get('level')=='ERROR':
        print('   ', x.get('taskId'), (x.get('message') or '')[:200])
" >&2 || true
  exit 1
fi

echo "==> 详情: $KESTRA_URL/ui/main/executions/$NS/$FLOW_ID/$EXEC_ID"
