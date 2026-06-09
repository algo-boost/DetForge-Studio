"""工具箱与 Catalog API。"""
from __future__ import annotations

from flask import Blueprint, jsonify, request

tools_bp = Blueprint('tools', __name__, url_prefix='/api')


@tools_bp.route('/tools', methods=['GET'])
def list_tools():
    from capabilities.registry import get_registry
    reg = get_registry()
    return jsonify({'success': True, 'data': reg.list_tools()})


@tools_bp.route('/tools/<tool_id>/execute', methods=['POST'])
def execute_tool(tool_id):
    from capabilities.base import RunContext
    from capabilities.registry import get_registry

    body = request.get_json(silent=True) or {}
    reg = get_registry()
    ctx = RunContext(
        run_id=body.get('run_id'),
        step_id=body.get('step_id'),
        params=body.get('params') or {},
        inputs=body.get('inputs') or {},
    )
    result = reg.execute(tool_id, ctx)
    return jsonify({
        'success': result.status != 'failed',
        'status': result.status,
        'outputs': result.outputs,
        'reason': result.reason,
    })


@tools_bp.route('/tools/stats', methods=['GET'])
def tool_stats():
    from capabilities.registry import get_registry
    return jsonify({'success': True, 'data': get_registry().usage_stats()})


@tools_bp.route('/catalog/status', methods=['GET'])
def catalog_status():
    from orchestration.catalog_sync import catalog_status as _status
    return jsonify({'success': True, 'data': _status()})


@tools_bp.route('/catalog/sync', methods=['POST'])
def catalog_sync():
    from orchestration.catalog_sync import sync_catalog
    dry_run = bool((request.get_json(silent=True) or {}).get('dry_run'))
    result = sync_catalog(dry_run=dry_run)
    return jsonify({'success': result.get('success', False), 'data': result})


@tools_bp.route('/catalog/refresh', methods=['POST'])
def catalog_refresh():
    """Webhook：Catalog PR 合并后触发同步。"""
    from orchestration.catalog_sync import sync_catalog
    result = sync_catalog()
    return jsonify({'success': result.get('success', False), 'data': result})


@tools_bp.route('/catalog/logs', methods=['GET'])
def catalog_logs():
    from orchestration.catalog_sync import list_sync_logs
    from studio.forge import forge_db
    limit = int(request.args.get('limit') or 20)
    logs = []
    try:
        if forge_db.schema_ready():
            logs = forge_db.list_catalog_sync_logs(limit=limit)
    except Exception:
        pass
    if not logs:
        logs = list_sync_logs(limit=limit)
    return jsonify({'success': True, 'data': logs})


@tools_bp.route('/pipelines', methods=['GET'])
def list_pipelines():
    from orchestration.loader import discover_pipelines
    pipelines = discover_pipelines()
    return jsonify({'success': True, 'data': pipelines})


@tools_bp.route('/workflows/agent-compile', methods=['POST'])
def workflow_agent_compile():
    from capabilities.registry import get_registry
    from orchestration.agent_compiler import build_agent_system_prompt, compile_agent_draft

    body = request.get_json(silent=True) or {}
    text = body.get('text') or body.get('draft') or ''
    if not text:
        return jsonify({'success': False, 'error': '缺少 text/draft'}), 400
    result = compile_agent_draft(text)
    result['system_prompt'] = build_agent_system_prompt(get_registry().list_tools())
    return jsonify({'success': result.get('success', False), 'data': result})


# 内存中暂停的演示 Flow（单实例 PoC）
_demo_flow_runs: dict[str, dict] = {}


@tools_bp.route('/flows/demo', methods=['GET'])
def flow_demo_info():
    from orchestration.flow_runner import find_pipeline
    try:
        defn, path = find_pipeline('welcome_demo')
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'welcome_demo 未找到'}), 404
    return jsonify({
        'success': True,
        'data': {
            'id': defn.get('id'),
            'name': defn.get('name'),
            'description': defn.get('description'),
            'path': path,
            'params_schema': defn.get('params_schema') or {},
            'nodes': defn.get('nodes') or [],
        },
    })


@tools_bp.route('/flows/run', methods=['POST'])
def flow_run():
    from orchestration.flow_runner import find_pipeline, run_flow

    body = request.get_json(silent=True) or {}
    flow_id = body.get('flow_id') or body.get('flow') or 'welcome_demo'
    try:
        defn, _path = find_pipeline(flow_id)
    except FileNotFoundError as e:
        return jsonify({'success': False, 'error': str(e)}), 404
    params = body.get('params') or {}
    auto_resume = bool(body.get('auto_resume'))
    resume_run_id = body.get('resume_run_id')

    if resume_run_id and resume_run_id in _demo_flow_runs:
        pending = _demo_flow_runs.pop(resume_run_id)
        defn = pending['defn']
        params = pending['params']
        step_outputs = pending['step_outputs']
        run_id = resume_run_id
        from capabilities.base import RunContext
        from capabilities.registry import init_registry

        reg = init_registry()
        nodes = defn.get('nodes') or []
        pause_id = pending['pause_at']
        seen = False
        step_results = list(pending.get('steps') or [])
        for node in nodes:
            if node['id'] == pause_id:
                seen = True
                fr_outputs = dict(step_outputs.get(pause_id) or {})
                fr_outputs.update({'waiting': False, 'approved_by': body.get('approved_by') or 'web-user'})
                step_outputs[pause_id] = fr_outputs
                step_results[-1]['status'] = 'done'
                step_results[-1]['outputs'] = fr_outputs
                continue
            if not seen:
                continue
            from orchestration.flow_runner import resolve_templates
            tool = node.get('tool') or node.get('kind')
            resolved = resolve_templates(node.get('params') or {}, params, step_outputs)
            ctx = RunContext(run_id=run_id, step_id=node['id'], params=resolved, inputs={'steps': step_outputs})
            result = reg.execute(tool, ctx)
            step_results.append({
                'step_id': node['id'],
                'tool': tool,
                'status': result.status,
                'params': resolved,
                'outputs': dict(result.outputs),
                'reason': result.reason,
            })
            step_outputs[node['id']] = dict(result.outputs)
            if result.status != 'done':
                payload = {
                    'defn': defn, 'params': params, 'step_outputs': step_outputs,
                    'pause_at': node['id'], 'steps': step_results,
                }
                _demo_flow_runs[run_id] = payload
                return jsonify({
                    'success': False,
                    'status': result.status,
                    'data': {
                        'flow_id': defn.get('id'),
                        'run_id': run_id,
                        'status': result.status,
                        'pause_at': node['id'],
                        'steps': step_results,
                    },
                })
        out = {
            'flow_id': defn.get('id'),
            'run_id': run_id,
            'status': 'done',
            'params': params,
            'steps': step_results,
        }
        return jsonify({'success': True, 'status': 'done', 'data': out})

    result = run_flow(defn, params, auto_resume=auto_resume)
    data = result.to_dict()
    if result.status == 'waiting_human':
        _demo_flow_runs[result.run_id] = {
            'defn': defn,
            'params': params,
            'step_outputs': {s.step_id: s.outputs for s in result.steps},
            'pause_at': result.pause_at,
            'steps': data['steps'],
        }
    return jsonify({
        'success': result.status == 'done',
        'status': result.status,
        'data': data,
    })


@tools_bp.route('/workflows/import', methods=['POST'])
def workflow_import():
    from studio.forge import forge_db

    body = request.get_json(silent=True) or {}
    pipeline = body.get('pipeline') or {}
    definition = body.get('definition')
    if not definition and pipeline:
        from orchestration.loader import pipeline_to_workflow_definition
        definition = pipeline_to_workflow_definition(pipeline)
    if not definition or not pipeline.get('id'):
        return jsonify({'success': False, 'error': '缺少 pipeline.id 与 definition'}), 400
    tpl = {
        'id': pipeline['id'],
        'name': pipeline.get('name') or pipeline['id'],
        'description': pipeline.get('description') or '',
        'version': int(pipeline.get('version') or 1),
        'builtin': 0,
        'definition': definition,
    }
    forge_db.upsert_workflow_template(tpl)
    return jsonify({'success': True, 'data': tpl})
