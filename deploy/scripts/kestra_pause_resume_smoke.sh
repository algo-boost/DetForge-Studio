#!/usr/bin/env bash
# Pause → IISP Resume API → SUCCESS（M2 Resume API 冒烟）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FLOW_FILE="$ROOT/deploy/flows/main_iisp.pause_resume_smoke.yaml"
KESTRA_URL="${KESTRA_URL:-http://127.0.0.1:8080}"
KESTRA_USER="${KESTRA_USER:-admin@kestra.io}"
KESTRA_PASSWORD="${KESTRA_PASSWORD:-Admin1234}"
IISP_URL="${IISP_URL:-http://127.0.0.1:5050}"
NS="iisp"
FLOW_ID="pause_resume_smoke"
AUTH=(-u "$KESTRA_USER:$KESTRA_PASSWORD")
KAPI="$KESTRA_URL/api/v1/main"

echo "==> 导入 Flow"
HTTP=$(curl -s -w '%{http_code}' -o /tmp/kestra_pause_flow.json "${AUTH[@]}" -X PUT "$KAPI/flows/$NS/$FLOW_ID" \
  -H "Content-Type: application/x-yaml" --data-binary @"$FLOW_FILE")
if [ "$HTTP" != "200" ]; then
  HTTP=$(curl -s -w '%{http_code}' -o /tmp/kestra_pause_flow.json "${AUTH[@]}" -X POST "$KAPI/flows" \
    -H "Content-Type: application/x-yaml" --data-binary @"$FLOW_FILE")
fi
[ "$HTTP" = "200" ] || { echo "导入失败 HTTP=$HTTP"; cat /tmp/kestra_pause_flow.json; exit 1; }
echo "    OK $NS/$FLOW_ID"

echo "==> 触发执行"
EXEC_ID=$(curl -sf "${AUTH[@]}" -X POST "$KAPI/executions/$NS/$FLOW_ID" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "    execution_id=$EXEC_ID"

echo "==> 等待 PAUSED"
for i in $(seq 1 24); do
  STATE=$(curl -sf "${AUTH[@]}" "$KAPI/executions/$EXEC_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',{}).get('current','?'))")
  echo "    [$i] state=$STATE"
  [ "$STATE" = "PAUSED" ] && break
  [ "$STATE" = "FAILED" ] && { echo "未进入 PAUSED"; exit 1; }
  sleep 2
done
[ "$STATE" = "PAUSED" ] || { echo "超时未 PAUSED"; exit 1; }

echo "==> IISP Resume API"
RES=$(curl -sf -X POST "$IISP_URL/v1/orchestration/resume" \
  -H "Content-Type: application/json" \
  -d "{\"execution_id\":\"$EXEC_ID\"}")
echo "$RES" | python3 -m json.tool

echo "==> 等待 SUCCESS"
for i in $(seq 1 24); do
  STATE=$(curl -sf "${AUTH[@]}" "$KAPI/executions/$EXEC_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',{}).get('current','?'))")
  echo "    [$i] state=$STATE"
  case "$STATE" in SUCCESS|FAILED) break ;; esac
  sleep 2
done

if [ "$STATE" = "SUCCESS" ]; then
  echo "==> Pause/Resume 冒烟通过"
else
  echo "==> 失败 state=$STATE" >&2
  exit 1
fi
