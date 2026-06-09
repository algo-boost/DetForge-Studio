"""Flask application factory."""
import os
from flask import Flask, request, jsonify

from server.routes import register_routes
from studio.paths import APP_ROOT

# 单次请求体上限（默认 256MB，覆盖批量图片上传）
MAX_CONTENT_LENGTH = int(os.environ.get('PC_MAX_CONTENT_MB', '256')) * 1024 * 1024


def _install_optional_auth(app):
    """可选 API Token 鉴权：仅当 config.json 配置了非空 api_token 时启用，默认关闭不破坏现状。

    校验请求头 X-API-Token 或查询参数 ?token=，仅作用于 /api/ 路由。
    """
    @app.before_request
    def _check_token():  # noqa: ANN202
        path = request.path or ''
        if not path.startswith('/api/') and not path.startswith('/viz/api/'):
            return None
        try:
            from server.core import load_config
            token = str(load_config().get('api_token') or '').strip()
        except Exception:
            token = ''
        if not token:
            return None  # 未配置 → 不鉴权
        sent = request.headers.get('X-API-Token') or request.args.get('token') or ''
        if sent != token:
            return jsonify({'success': False, 'error': '未授权（缺少或错误的 API Token）'}), 401
        return None


def create_app():
    base_dir = APP_ROOT
    # 静态资源由 spa 蓝图从 frontend/dist 提供（含 dist/assets/），
    # 勿设 static_url_path='/assets'，否则会与 Vite 产物路径冲突导致 JS 404、白屏。
    app = Flask(__name__)
    app.config['UPLOAD_FOLDER'] = os.path.join(base_dir, 'exports')
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    try:
        from studio.lifecycle import install_hooks, startup as lifecycle_startup
        install_hooks()
        lifecycle_startup()
    except Exception as e:  # noqa: BLE001
        print(f'⚠️ 生命周期钩子初始化失败: {e}')

    try:
        from capabilities.registry import init_registry
        init_registry()
    except Exception as e:  # noqa: BLE001
        print(f'⚠️ Capability Registry 初始化失败: {e}')

    if os.environ.get('IISP_CATALOG_SYNC_ON_START', '0').lower() in ('1', 'true', 'yes'):
        try:
            from orchestration.catalog_sync import sync_catalog
            sync_catalog()
        except Exception as e:  # noqa: BLE001
            print(f'⚠️ Catalog 启动同步失败: {e}')

    _install_optional_auth(app)
    register_routes(app)

    try:
        from studio.query import query_jobs
        query_jobs.init_query_jobs(app)
    except Exception as e:  # noqa: BLE001
        print(f'⚠️ 查询任务队列初始化失败: {e}')

    try:
        from studio.export import archive_jobs
        archive_jobs.init_archive_jobs(app)
    except Exception as e:  # noqa: BLE001
        print(f'⚠️ 归档任务队列初始化失败: {e}')

    # 后台作业 worker（PID 防重复；PC_NO_WORKER=1 可禁用）
    try:
        import sys
        if base_dir not in sys.path:
            sys.path.insert(0, base_dir)
        from worker import maybe_start_in_process
        maybe_start_in_process()
    except Exception as e:  # noqa: BLE001
        print(f"⚠️ worker 自动启动失败（可命令行手动启动 python worker.py）: {e}")

    if os.environ.get('PC_NO_WORKFLOW_SCHEDULER') != '1':
        try:
            from studio.forge.workflow_scheduler import init_workflow_scheduler
            init_workflow_scheduler(app)
        except Exception as e:  # noqa: BLE001
            print(f'⚠️ 工作流调度器启动失败: {e}')

    @app.after_request
    def add_cors_headers(response):
        if os.environ.get('PC_DEV_CORS') == '1':
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, DELETE, OPTIONS'
        return response

    return app
