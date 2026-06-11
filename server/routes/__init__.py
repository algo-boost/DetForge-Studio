from server.routes.orchestration import orchestration_bp
from server.routes.api import api_bp
from server.routes.forge import forge_bp
from server.routes.gateway import gateway_bp
from server.routes.tools import tools_bp
from server.routes.workbench import workbench_bp
from server.routes.tool_integration import tool_integration_bp
from server.routes.query_tool import query_tool_bp
from server.routes.query_ui import ensure_query_tool_mounted
from server.routes.viz import viz_bp, ensure_viz_mounted
from server.routes.unify import unify_bp, ensure_unify_mounted
from server.routes.spa import spa_bp
from server.routes.kestra_embed import kestra_embed_bp


def register_routes(app):
    app.register_blueprint(gateway_bp)
    app.register_blueprint(orchestration_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(forge_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(workbench_bp)
    app.register_blueprint(tool_integration_bp)
    app.register_blueprint(query_tool_bp)
    app.register_blueprint(viz_bp)
    app.register_blueprint(unify_bp)
    ensure_query_tool_mounted(app)
    ensure_viz_mounted(app)
    ensure_unify_mounted(app)
    app.register_blueprint(kestra_embed_bp)
    app.register_blueprint(spa_bp)
