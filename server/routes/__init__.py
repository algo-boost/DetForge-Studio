from server.routes.api import api_bp
from server.routes.forge import forge_bp
from server.routes.viz import viz_bp, ensure_viz_mounted
from server.routes.unify import unify_bp, ensure_unify_mounted
from server.routes.spa import spa_bp


def register_routes(app):
    app.register_blueprint(api_bp)
    app.register_blueprint(forge_bp)
    app.register_blueprint(viz_bp)
    app.register_blueprint(unify_bp)
    ensure_viz_mounted(app)
    ensure_unify_mounted(app)
    app.register_blueprint(spa_bp)
