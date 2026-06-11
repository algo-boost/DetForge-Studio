"""Kestra UI 同源反向代理 — iframe 免登录（注入 BASIC_AUTH Cookie + 路径改写）。"""
from __future__ import annotations

import base64
import os
import urllib.error
import urllib.request
from typing import Iterable

from flask import Blueprint, Response, request

from orchestration import kestra_client as kc

kestra_embed_bp = Blueprint('kestra_embed', __name__)

_PREFIX = '/kestra-embed'
_HOP_BY_HOP = {
    'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
    'te', 'trailers', 'transfer-encoding', 'upgrade', 'host', 'content-length',
}

_REWRITE_TYPES = ('text/html', 'application/javascript', 'text/javascript', 'application/json')


def _embed_enabled() -> bool:
    return os.environ.get('KESTRA_EMBED_PROXY', '1').lower() not in ('0', 'false', 'no')


def _credentials() -> tuple[str, str]:
    cfg = kc._config()  # noqa: SLF001 — shared env with kestra_client
    return cfg['user'], cfg['password']


def _auth_header(user: str, password: str) -> str:
    token = base64.b64encode(f'{user}:{password}'.encode()).decode('ascii')
    return f'Basic {token}'


def _rewrite_body(body: bytes, content_type: str) -> bytes:
    if not any(t in (content_type or '') for t in _REWRITE_TYPES):
        return body
    try:
        text = body.decode('utf-8')
    except UnicodeDecodeError:
        return body
    # Kestra SPA 使用站点根路径 /api、/ui，改写为同源代理前缀
    if _PREFIX in text:
        return text.encode('utf-8')
    for old, new in (
        ('"/api/', f'"{_PREFIX}/api/'),
        ("'/api/", f"'{_PREFIX}/api/"),
        ('"/ui/', f'"{_PREFIX}/ui/'),
        ("'/ui/", f"'{_PREFIX}/ui/"),
        ('src="/', f'src="{_PREFIX}/'),
        ("src='/", f"src='{_PREFIX}/"),
        ('href="/favicon', f'href="{_PREFIX}/favicon'),
        ('href="/ui/', f'href="{_PREFIX}/ui/'),
    ):
        text = text.replace(old, new)
    return text.encode('utf-8')


def _forward_headers(incoming: Iterable[tuple[str, str]], user: str, password: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in incoming:
        if key.lower() in _HOP_BY_HOP:
            continue
        out[key] = value
    out['Authorization'] = _auth_header(user, password)
    return out


@kestra_embed_bp.route(f'{_PREFIX}/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
@kestra_embed_bp.route(f'{_PREFIX}/<path:path>', methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'])
def kestra_embed_proxy(path: str):
    if not kc.is_enabled():
        return Response('Kestra 未启用', status=503, mimetype='text/plain')
    if not _embed_enabled():
        return Response('Kestra 嵌入代理已关闭', status=503, mimetype='text/plain')

    cfg = kc._config()  # noqa: SLF001
    user, password = _credentials()
    upstream = f"{cfg['base_url'].rstrip('/')}/{path}"
    if request.query_string:
        upstream += f'?{request.query_string.decode("utf-8")}'

    data = request.get_data()
    headers = _forward_headers(request.headers, user, password)
    req = urllib.request.Request(
        upstream,
        data=data if data else None,
        method=request.method,
        headers=headers,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as upstream_resp:
            body = upstream_resp.read()
            content_type = upstream_resp.headers.get('Content-Type', '')
            body = _rewrite_body(body, content_type)
            out = Response(body, status=upstream_resp.status)
            for key, value in upstream_resp.headers.items():
                lk = key.lower()
                if lk in _HOP_BY_HOP or lk == 'set-cookie':
                    continue
                out.headers[key] = value
    except urllib.error.HTTPError as exc:
        body = exc.read()
        content_type = exc.headers.get('Content-Type', '') if exc.headers else ''
        body = _rewrite_body(body, content_type)
        out = Response(body, status=exc.code)
        if exc.headers:
            for key, value in exc.headers.items():
                if key.lower() not in _HOP_BY_HOP:
                    out.headers[key] = value
    except urllib.error.URLError as exc:
        return Response(f'Kestra 不可达: {exc.reason}', status=502, mimetype='text/plain')

    cookie_val = base64.b64encode(f'{user}:{password}'.encode()).decode('ascii')
    out.headers.add('Set-Cookie', f'BASIC_AUTH={cookie_val}; Path={_PREFIX}; SameSite=Lax')
    return out
