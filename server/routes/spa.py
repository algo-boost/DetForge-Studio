"""Serve React SPA."""
import os
from flask import Blueprint, abort, make_response, send_from_directory

from studio.paths import resource_path

spa_bp = Blueprint('spa', __name__)

FRONTEND_DIST = resource_path('frontend', 'dist')


def _dist_ready():
    return os.path.isfile(os.path.join(FRONTEND_DIST, 'index.html'))


@spa_bp.route('/', defaults={'path': ''}, methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
@spa_bp.route('/<path:path>', methods=['GET', 'HEAD', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'])
def serve_spa(path):
    if (
        path.startswith('api/')
        or path == 'viz' or path.startswith('viz/')
        or path == 'unify' or path.startswith('unify/')
    ):
        abort(404)

    if not _dist_ready():
        abort(503, description='React 前端未构建，请运行: cd frontend && npm install && npm run build')

    if path and os.path.isfile(os.path.join(FRONTEND_DIST, path)):
        resp = make_response(send_from_directory(FRONTEND_DIST, path))
        # 带 hash 的静态资源可长期缓存；index.html 禁止缓存，避免 JS/CSS 哈希不一致
        if path.startswith('assets/'):
            resp.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return resp

    resp = make_response(send_from_directory(FRONTEND_DIST, 'index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    return resp
