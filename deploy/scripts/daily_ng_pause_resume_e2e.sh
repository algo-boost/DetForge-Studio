#!/usr/bin/env bash
# M2-run：daily_ng Pause → 回传 COCO → IISP Resume → SUCCESS
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FLOW_ID="${FLOW_ID:-daily_ng_curation_smoke}"
FLOW_FILE="${FLOW_FILE:-$ROOT/iisp-catalog/pipelines/kestra/${FLOW_ID}.yaml}"
KESTRA_URL="${KESTRA_URL:-http://127.0.0.1:8080}"
KESTRA_USER="${KESTRA_USER:-admin@kestra.io}"
KESTRA_PASSWORD="${KESTRA_PASSWORD:-Admin1234}"
IISP_URL="${IISP_URL:-http://127.0.0.1:5050}"
NS="iisp"
AUTH=(-u "$KESTRA_USER:$KESTRA_PASSWORD")
KAPI="$KESTRA_URL/api/v1/main"

kcurl() {
  curl -sf --connect-timeout 10 --max-time 120 -u "$KESTRA_USER:$KESTRA_PASSWORD" "$@"
}

echo "==> IISP Gateway + forge schema"
curl -sf "$IISP_URL/v1/tools" >/dev/null
echo "    OK $IISP_URL/v1/tools"
SCHEMA_HTTP=$(curl -s -o /tmp/iisp_schema.json -w '%{http_code}' -X POST "$IISP_URL/api/forge/schema/init" || true)
echo "    schema/init HTTP=${SCHEMA_HTTP:-000}"

echo "==> Kestra health"
for i in $(seq 1 30); do
  if kcurl "$KESTRA_URL/" >/dev/null 2>&1; then
    echo "    OK $KESTRA_URL"
    break
  fi
  sleep 2
  if [ "$i" -eq 30 ]; then
    echo "Kestra 未就绪: $KESTRA_URL" >&2
    exit 1
  fi
done

if [ ! -f "$FLOW_FILE" ]; then
  echo "Flow 文件不存在: $FLOW_FILE" >&2
  exit 1
fi

import_flow() {
  local flow_id="$1"
  local flow_file="$2"
  local http get_http

  get_http=$(curl -s --connect-timeout 10 --max-time 15 -w '%{http_code}' -o /dev/null \
    -u "$KESTRA_USER:$KESTRA_PASSWORD" "$KAPI/flows/$NS/$flow_id")
  if [ "$get_http" = "200" ]; then
    echo "    skip import: $NS/$flow_id already exists"
    return 0
  fi

  echo "==> import flow POST $KAPI/flows -> $NS/$flow_id"
  http=$(curl -s --connect-timeout 10 --max-time 90 -w '%{http_code}' -o /tmp/kestra_m2_flow.json \
    -u "$KESTRA_USER:$KESTRA_PASSWORD" -X POST "$KAPI/flows" \
    -H "Content-Type: application/x-yaml" \
    --data-binary @"$flow_file")
  if [ "$http" = "200" ]; then
    echo "    OK $NS/$flow_id"
    return 0
  fi

  echo "    POST 失败 HTTP=$http，尝试 PUT"
  http=$(curl -s --connect-timeout 10 --max-time 90 -w '%{http_code}' -o /tmp/kestra_m2_flow.json \
    -u "$KESTRA_USER:$KESTRA_PASSWORD" -X PUT "$KAPI/flows/$NS/$flow_id" \
    -H "Content-Type: application/x-yaml" \
    --data-binary @"$flow_file")
  if [ "$http" != "200" ]; then
    echo "    导入失败 HTTP=$http" >&2
    cat /tmp/kestra_m2_flow.json >&2
    echo "    提示: Kestra PUT 复杂 Flow 可能 OOM，可 docker restart deploy-kestra-1 后重试" >&2
    exit 1
  fi
  echo "    OK $NS/$flow_id"
}

import_flow "$FLOW_ID" "$FLOW_FILE"

echo "==> 触发执行"
EXEC_ID=$(kcurl -X POST "$KAPI/executions/$NS/$FLOW_ID" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
echo "    execution_id=$EXEC_ID"

echo "==> 等待 PAUSED"
STATE=""
for i in $(seq 1 36); do
  STATE=$(kcurl "$KAPI/executions/$EXEC_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',{}).get('current','?'))")
  echo "    [$i] state=$STATE"
  case "$STATE" in
    PAUSED) break ;;
    SUCCESS)
      echo "    未经过 Pause 即 SUCCESS（可能 batch 已 imported）" >&2
      exit 1
      ;;
    FAILED|KILLED|CANCELLED)
      echo "    执行失败 state=$STATE" >&2
      exit 1
      ;;
  esac
  sleep 5
done
[ "$STATE" = "PAUSED" ] || { echo "超时未 PAUSED (state=$STATE)" >&2; exit 1; }

echo "==> 解析 batch_id 并回传 COCO"
export IISP_URL EXEC_ID="$EXEC_ID" KESTRA_URL KESTRA_AUTH="${KESTRA_USER}:${KESTRA_PASSWORD}"
read -r BATCH_ID EXPORT_DIR <<<"$(python3 <<'PY'
import json, os, sys, urllib.request

iisp = os.environ['IISP_URL']
exec_id = os.environ['EXEC_ID']
auth = os.environ.get('KESTRA_AUTH', '')
kestra = os.environ['KESTRA_URL']
kapi = f"{kestra}/api/v1/main"

req = urllib.request.Request(f"{kapi}/executions/{exec_id}")
if auth:
    import base64
    req.add_header('Authorization', 'Basic ' + base64.b64encode(auth.encode()).decode())
with urllib.request.urlopen(req) as resp:
    execution = json.load(resp)

batch_id = None
for task in execution.get('taskRunList') or []:
    if task.get('taskId') != 'batch':
        continue
    body = (task.get('outputs') or {}).get('body') or ''
    if not body:
        continue
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        continue
    batch_id = (payload.get('outputs') or {}).get('batch_id')
    if batch_id is not None:
        batch_id = str(batch_id)
        break

if not batch_id:
    import re
    batch_re = re.compile(r'batch_id[=:]\s*([^\s;}\]]+)', re.I)
    for task in execution.get('taskRunList') or []:
        desc = str(task.get('description') or '')
        match = batch_re.search(desc)
        if match:
            batch_id = match.group(1).strip("'\"")
            break
        if task.get('taskId') == 'human_edit':
            for token in desc.replace('=', ' ').split():
                if token.isdigit():
                    batch_id = token
                    break
        if batch_id:
            break

if not batch_id:
    sys.stderr.write('cannot parse batch_id from execution\n')
    sys.exit(1)

with urllib.request.urlopen(f"{iisp}/api/forge/curation/{batch_id}") as resp:
    batch = json.load(resp).get('data') or {}
export_dir = batch.get('export_dir') or ''
coco_path = os.path.join(export_dir, '_annotations.coco.json') if export_dir else ''
print(batch_id, export_dir)

if coco_path and os.path.isfile(coco_path):
    with open(coco_path, encoding='utf-8') as f:
        coco_text = f.read()
    body = json.dumps({'coco_json': coco_text, 'filename': '_annotations.coco.json'}).encode('utf-8')
    imp = urllib.request.Request(
        f"{iisp}/api/forge/curation/{batch_id}/import",
        data=body,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    with urllib.request.urlopen(imp) as resp:
        result = json.load(resp)
    if not result.get('success'):
        sys.stderr.write(f"import 失败: {result}\\n")
        sys.exit(1)
    print(f"    imported COCO from {coco_path}", file=sys.stderr)
else:
    sys.stderr.write(f"export_dir 无 COCO: {export_dir}\\n")
    sys.exit(1)
PY
)"
echo "    batch_id=$BATCH_ID export_dir=$EXPORT_DIR"

echo "==> IISP Resume API"
RES=$(curl -sf -X POST "$IISP_URL/v1/orchestration/resume" \
  -H "Content-Type: application/json" \
  -d "{\"execution_id\":\"$EXEC_ID\"}")
echo "$RES" | python3 -m json.tool

echo "==> 等待 SUCCESS"
for i in $(seq 1 36); do
  STATE=$(kcurl "$KAPI/executions/$EXEC_ID" | python3 -c "import json,sys; print(json.load(sys.stdin).get('state',{}).get('current','?'))")
  echo "    [$i] state=$STATE"
  case "$STATE" in SUCCESS|FAILED|KILLED|CANCELLED) break ;; esac
  sleep 5
done

if [ "$STATE" = "SUCCESS" ]; then
  echo "==> M2-run 全链路通过 (Pause → COCO → Resume → SUCCESS)"
  echo "    batch_id=$BATCH_ID"
  echo "    $KESTRA_URL/ui/main/executions/$NS/$FLOW_ID/$EXEC_ID"
else
  echo "==> 失败 state=$STATE" >&2
  kcurl "$KAPI/logs/$EXEC_ID" | python3 -c "
import json,sys
for x in json.load(sys.stdin):
    if x.get('level') in ('ERROR','WARN'):
        print('   ', x.get('taskId'), (x.get('message') or '')[:240])
" >&2 || true
  exit 1
fi
