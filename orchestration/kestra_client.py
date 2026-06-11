"""Kestra Hub API 薄客户端（Resume、查询 PAUSED 执行）。"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class KestraError(Exception):
    def __init__(self, message: str, *, status_code: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _config() -> dict[str, str]:
    return {
        'base_url': os.environ.get('KESTRA_URL', 'http://127.0.0.1:8080').rstrip('/'),
        'user': os.environ.get('KESTRA_USER', 'admin@kestra.io'),
        'password': os.environ.get('KESTRA_PASSWORD', 'Admin1234'),
        'tenant': os.environ.get('KESTRA_TENANT', 'main'),
    }


def is_enabled() -> bool:
    return os.environ.get('KESTRA_ENABLED', '1').lower() not in ('0', 'false', 'no')


def _auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f'{user}:{password}'.encode()).decode('ascii')
    return f'Basic {token}'


def _request(
    method: str,
    path: str,
    *,
    data: bytes | None = None,
    content_type: str | None = None,
    accept_json: bool = True,
) -> Any:
    cfg = _config()
    url = f"{cfg['base_url']}{path}"
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', _auth_header(cfg['user'], cfg['password']))
    if content_type:
        req.add_header('Content-Type', content_type)
    if accept_json:
        req.add_header('Accept', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read()
            if not raw:
                return None
            if accept_json:
                return json.loads(raw.decode('utf-8'))
            return raw
    except urllib.error.HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')
        raise KestraError(
            f'Kestra HTTP {exc.code}: {body[:300]}',
            status_code=exc.code,
            body=body,
        ) from exc
    except urllib.error.URLError as exc:
        raise KestraError(f'Kestra 不可达: {exc.reason}') from exc


def _multipart_body(fields: dict[str, str] | None = None) -> tuple[bytes, str]:
    boundary = '----iisp-kestra-boundary'
    lines: list[str] = []
    for key, value in (fields or {}).items():
        lines.append(f'--{boundary}')
        lines.append(f'Content-Disposition: form-data; name="{key}"')
        lines.append('')
        lines.append(str(value))
    lines.append(f'--{boundary}--')
    lines.append('')
    payload = '\r\n'.join(lines).encode('utf-8')
    return payload, f'multipart/form-data; boundary={boundary}'


def get_execution(execution_id: str) -> dict:
    tenant = _config()['tenant']
    return _request('GET', f'/api/v1/{tenant}/executions/{execution_id}')


def list_paused_executions(*, limit: int = 20, namespace: str | None = None) -> list[dict]:
    tenant = _config()['tenant']
    query: dict[str, str] = {
        'page': '1',
        'size': str(max(1, min(limit, 100))),
        'filters[state][EQUALS]': 'PAUSED',
    }
    if namespace:
        query['filters[namespace][EQUALS]'] = namespace
    qs = urllib.parse.urlencode(query)
    data = _request('GET', f'/api/v1/{tenant}/executions/search?{qs}')
    return list((data or {}).get('results') or [])


def resume_execution(execution_id: str, *, inputs: dict[str, Any] | None = None) -> dict:
    tenant = _config()['tenant']
    fields = {str(k): str(v) for k, v in (inputs or {}).items()}
    body, content_type = _multipart_body(fields)
    _request(
        'POST',
        f'/api/v1/{tenant}/executions/{execution_id}/resume',
        data=body,
        content_type=content_type,
        accept_json=False,
    )
    execution = get_execution(execution_id)
    state = ((execution or {}).get('state') or {}).get('current')
    return {'execution_id': execution_id, 'state': state}


def _serialize_input_value(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def execute_flow(
    flow_id: str,
    *,
    namespace: str = 'iisp',
    inputs: dict[str, Any] | None = None,
) -> dict:
    """触发 Kestra Flow 执行。"""
    tenant = _config()['tenant']
    path = f'/api/v1/{tenant}/executions/{namespace}/{flow_id}'
    body_bytes = None
    content_type = None
    if inputs:
        body_bytes, content_type = _multipart_body(
            {str(k): _serialize_input_value(v) for k, v in inputs.items()}
        )
    data = _request('POST', path, data=body_bytes, content_type=content_type)
    ex_id = (data or {}).get('id')
    ns = (data or {}).get('namespace') or namespace
    fid = (data or {}).get('flowId') or flow_id
    state = ((data or {}).get('state') or {}).get('current')
    cfg = _config()
    kestra_url = (
        f"{cfg['base_url']}/ui/{cfg['tenant']}/executions/{ns}/{fid}/{ex_id}"
        if ex_id else None
    )
    return {
        'execution_id': ex_id,
        'namespace': ns,
        'flow_id': fid,
        'state': state,
        'kestra_url': kestra_url,
        'raw': data,
    }


_BATCH_ID_RE = re.compile(r'batch_id[=:]\s*([^\s;}\]]+)', re.I)


def extract_batch_id(execution: dict) -> str | None:
    for task in execution.get('taskRunList') or []:
        if task.get('taskId') == 'batch':
            body = (task.get('outputs') or {}).get('body') or ''
            if body:
                try:
                    payload = json.loads(body)
                    batch_id = (payload.get('outputs') or {}).get('batch_id')
                    if batch_id is not None:
                        return str(batch_id)
                except (TypeError, ValueError):
                    pass
    for task in execution.get('taskRunList') or []:
        if task.get('state', {}).get('current') != 'PAUSED':
            continue
        desc = str(task.get('description') or '')
        match = _BATCH_ID_RE.search(desc)
        if match:
            return match.group(1).strip("'\"")
    return None


def studio_config(*, namespace: str = 'iisp', use_proxy: bool | None = None) -> dict:
    """Kestra UI 嵌入配置（Shell iframe）。"""
    import os

    cfg = _config()
    tenant = cfg['tenant']
    base = cfg['base_url']
    ns = namespace or 'iisp'
    ui_root = f'{base}/ui/{tenant}'
    proxy_on = use_proxy
    if proxy_on is None:
        proxy_on = os.environ.get('KESTRA_EMBED_PROXY', '1').lower() not in ('0', 'false', 'no')
    embed_path = f'/ui/{tenant}/flows/{ns}'
    if proxy_on and is_enabled():
        embed_url = f'/kestra-embed{embed_path}'
        external_url = f'{ui_root}/flows/{ns}'
    else:
        embed_url = f'{ui_root}/flows/{ns}'
        external_url = embed_url
    return {
        'enabled': is_enabled(),
        'base_url': base,
        'tenant': tenant,
        'namespace': ns,
        'embed_url': embed_url,
        'external_url': external_url,
        'proxy_enabled': bool(proxy_on),
        'executions_url': f'{ui_root}/executions',
        'ui_root': ui_root,
    }


def summarize_execution(execution: dict) -> dict:
    cfg = _config()
    ex_id = execution.get('id')
    ns = execution.get('namespace') or 'iisp'
    flow_id = execution.get('flowId') or ''
    state = ((execution.get('state') or {}).get('current') or '').upper()
    batch_id = extract_batch_id(execution) if state == 'PAUSED' else None
    return {
        'execution_id': ex_id,
        'namespace': ns,
        'flow_id': flow_id,
        'state': state,
        'batch_id': batch_id,
        'ui_url': f'/curation?batch_id={batch_id}' if batch_id else None,
        'kestra_url': f"{cfg['base_url']}/ui/{cfg['tenant']}/executions/{ns}/{flow_id}/{ex_id}",
        'started_at': ((execution.get('state') or {}).get('startDate')),
    }


def summarize_paused(execution: dict) -> dict:
    out = summarize_execution(execution)
    out['status'] = 'waiting_human'
    return out
