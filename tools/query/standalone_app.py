"""Query 工具独立部署 Flask 应用（UI + REST + Gateway invoke）。"""
from __future__ import annotations

import os
import sys

from flask import Flask, jsonify, request

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from server.tool_integration import get_integration_mode, get_remote_url


def get_query_integration_mode(config=None):
    return get_integration_mode('query', config)


def create_standalone_app() -> Flask:
    from capabilities.base import RunContext
    from server.gateway.contract import result_to_v1
    from server.tool_integration import build_integration_payload
    from tools.query.capability import QueryCapability
    from tools.query.rest_routes import register_query_rest_routes
    from tools.query.ui_server import is_query_tool_ui_built, register_query_ui_routes, resolve_query_tool_ui_root

    app = Flask(__name__)
    cap = QueryCapability()

    register_query_rest_routes(app)

    @app.get('/health')
    def health():
        return jsonify({'ok': True, 'tool': 'query', 'mode': 'standalone'})

    @app.get('/api/query-tool/status')
    @app.get('/api/tools/query/integration')
    def status():
        return jsonify(build_integration_payload(
            'query',
            extra={
                'integration': 'standalone',
                'built': is_query_tool_ui_built(),
                'ui_root': resolve_query_tool_ui_root() or None,
                'invoke': '/v1/tools/query/invoke',
                'available': is_query_tool_ui_built(),
                'mounted': True,
            },
        ))

    @app.post('/v1/invoke')
    @app.post('/v1/tools/query/invoke')
    def invoke():
        body = request.get_json(silent=True) or {}
        ctx = RunContext(
            run_id=body.get('run_id'),
            step_id=body.get('step_id'),
            params=body.get('params') or {},
            inputs=body.get('inputs') or {},
        )
        result = cap.execute(ctx)
        status_code = 200 if result.status in ('done', 'skipped', 'waiting_human') else 500
        return jsonify(result_to_v1(result)), status_code

    if not register_query_ui_routes(app, mount_prefix=''):
        print('⚠️ Query standalone: UI 未构建，仅 REST/invoke 可用')

    print('✓ Query 独立部署：REST + invoke + UI(/)')
    return app
