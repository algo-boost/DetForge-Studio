"""Query REST 路由注册 — 集成 / 独立部署共用。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from tools.query import rest as query_rest

query_rest_bp = Blueprint('query_rest', __name__)


@query_rest_bp.route('/api/query', methods=['POST'])
def post_query():
    body, status = query_rest.handle_post_query(request.get_json(silent=True))
    return jsonify(body), status


@query_rest_bp.route('/api/query/jobs', methods=['POST'])
def create_query_job():
    body, status = query_rest.handle_create_query_job(request.get_json(silent=True))
    return jsonify(body), status


@query_rest_bp.route('/api/query/jobs', methods=['GET'])
def list_query_jobs():
    limit = min(100, int(request.args.get('limit', 30)))
    active_only = request.args.get('active_only', '').lower() in ('1', 'true', 'yes')
    body, status = query_rest.handle_list_query_jobs(limit=limit, active_only=active_only)
    return jsonify(body), status


@query_rest_bp.route('/api/query/jobs/<job_id>', methods=['GET'])
def get_query_job(job_id):
    body, status = query_rest.handle_get_query_job(job_id)
    return jsonify(body), status


@query_rest_bp.route('/api/query/task/<task_id>', methods=['GET'])
def get_query_task(task_id):
    body, status = query_rest.handle_get_query_task(task_id)
    return jsonify(body), status


@query_rest_bp.route('/api/strategies', methods=['GET'])
def list_strategies():
    body, status = query_rest.handle_list_strategies()
    return jsonify(body), status


@query_rest_bp.route('/api/strategies/<strategy_id>', methods=['GET'])
def get_strategy(strategy_id):
    body, status = query_rest.handle_get_strategy(strategy_id)
    return jsonify(body), status


@query_rest_bp.route('/api/strategies/<strategy_id>/variables', methods=['GET'])
def get_strategy_variables(strategy_id):
    body, status = query_rest.handle_get_strategy_variables(strategy_id)
    return jsonify(body), status


@query_rest_bp.route('/api/strategies', methods=['POST'])
def save_strategy():
    body, status = query_rest.handle_save_strategy(request.get_json(silent=True))
    return jsonify(body), status


@query_rest_bp.route('/api/strategies/<strategy_id>', methods=['DELETE'])
def delete_strategy(strategy_id):
    body, status = query_rest.handle_delete_strategy(strategy_id)
    return jsonify(body), status


@query_rest_bp.route('/api/strategies/execute', methods=['POST'])
def execute_strategy():
    body, status = query_rest.handle_execute_strategy(request.get_json(silent=True))
    return jsonify(body), status


@query_rest_bp.route('/api/strategies/compile-pipeline', methods=['POST'])
def compile_strategy_pipeline():
    body, status = query_rest.handle_compile_strategy_pipeline(request.get_json(silent=True))
    return jsonify(body), status


def register_query_rest_routes(app) -> None:
    app.register_blueprint(query_rest_bp)
