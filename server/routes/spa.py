"""Serve React SPA."""
import os
from flask import Blueprint, send_from_directory, abort

spa_bp = Blueprint('spa', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRONTEND_DIST = os.path.join(BASE_DIR, 'frontend', 'dist')


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
        return send_from_directory(FRONTEND_DIST, path)
    return send_from_directory(FRONTEND_DIST, 'index.html')
