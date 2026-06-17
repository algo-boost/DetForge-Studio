"""工具箱与 Catalog API。"""
from __future__ import annotations

import json as _json

from flask import Blueprint, Response, jsonify, request

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


def resume_demo_flow(run_id: str, *, approved_by: str = 'web-user') -> dict:
    """继续内存中的演示 Flow（供 Web / flows service 共用）。"""
    if run_id not in _demo_flow_runs:
        raise ValueError('演示运行不存在或已结束')
    pending = _demo_flow_runs.pop(run_id)
    defn = pending['defn']
    params = pending['params']
    step_outputs = pending['step_outputs']
    from capabilities.base import RunContext
    from capabilities.registry import init_registry
    from orchestration.flow_runner import resolve_templates

    reg = init_registry()
    nodes = defn.get('nodes') or []
    pause_id = pending['pause_at']
    seen = False
    step_results = list(pending.get('steps') or [])
    for node in nodes:
        if node['id'] == pause_id:
            seen = True
            fr_outputs = dict(step_outputs.get(pause_id) or {})
            fr_outputs.update({'waiting': False, 'approved_by': approved_by})
            step_outputs[pause_id] = fr_outputs
            step_results[-1]['status'] = 'done'
            step_results[-1]['outputs'] = fr_outputs
            continue
        if not seen:
            continue
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
            return {
                'success': False,
                'status': result.status,
                'data': {
                    'flow_id': defn.get('id'),
                    'run_id': run_id,
                    'status': result.status,
                    'pause_at': node['id'],
                    'steps': step_results,
                },
            }
    return {
        'success': True,
        'status': 'done',
        'data': {
            'flow_id': defn.get('id'),
            'run_id': run_id,
            'status': 'done',
            'params': params,
            'steps': step_results,
        },
    }


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
        try:
            payload = resume_demo_flow(resume_run_id, approved_by=body.get('approved_by') or 'web-user')
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 404
        return jsonify(payload)

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


@tools_bp.route('/flows/list', methods=['GET'])
def flows_list():
    from server.services import flows as fs
    return jsonify({'success': True, 'data': fs.list_flow_catalog()})


@tools_bp.route('/flows/releases', methods=['GET'])
def flows_releases():
    from server.services import flows as fs
    return jsonify({'success': True, 'data': fs.list_releases()})


@tools_bp.route('/flows/runs', methods=['GET'])
def flows_runs_list():
    from server.services import flows as fs
    status = (request.args.get('status') or '').strip() or None
    flow_id = (request.args.get('flow_id') or '').strip() or None
    limit = int(request.args.get('limit') or 50)
    return jsonify({
        'success': True,
        'data': fs.list_flow_runs(status=status, flow_id=flow_id, limit=limit),
    })


@tools_bp.route('/flows/runs/<path:run_key>', methods=['GET'])
def flows_run_get(run_key):
    from server.services import flows as fs
    detail = fs.get_flow_run(run_key)
    if not detail:
        return jsonify({'success': False, 'error': '运行记录不存在'}), 404
    return jsonify({'success': True, 'data': detail})


@tools_bp.route('/flows/runs/<path:run_key>/resume', methods=['POST'])
def flows_run_resume(run_key):
    from server.services import flows as fs
    body = request.get_json(silent=True) or {}
    try:
        result = fs.resume_flow_run(run_key, body)
    except ValueError as exc:
        return jsonify({'success': False, 'error': str(exc)}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    return jsonify({'success': True, 'data': result})


@tools_bp.route('/flows/pipelines/<flow_id>/yaml', methods=['GET'])
def flows_pipeline_yaml(flow_id):
    from server.services import flows as fs
    try:
        data = fs.get_pipeline_yaml(flow_id)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'Flow 未找到: {flow_id}'}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    return jsonify({'success': True, 'data': data})


@tools_bp.route('/flows/pipelines/<flow_id>/graph', methods=['GET'])
def flows_pipeline_graph(flow_id):
    from server.services import flows as fs
    try:
        data = fs.get_flow_graph(flow_id)
    except FileNotFoundError:
        return jsonify({'success': False, 'error': f'Flow 未找到: {flow_id}'}), 404
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    return jsonify({'success': True, 'data': data})


@tools_bp.route('/flows/agent/context', methods=['GET'])
def flows_agent_context():
    from orchestration.flow_agent_service import get_compose_context

    flow_id = request.args.get('flow_id') or None
    try:
        data = get_compose_context(flow_id)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    return jsonify({'success': True, 'data': data})


@tools_bp.route('/flows/agent/compose', methods=['POST'])
def flows_agent_compose():
    from orchestration.flow_agent_service import compose_from_description

    body = request.get_json(silent=True) or {}
    message = body.get('message') or body.get('description') or ''
    if not str(message).strip():
        return jsonify({'success': False, 'error': '缺少 message'}), 400
    try:
        data = compose_from_description(
            message,
            flow_id=body.get('flow_id'),
            history=body.get('history'),
        )
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    return jsonify({'success': data.get('success', False), 'data': data})


@tools_bp.route('/flows/agent/compose/stream', methods=['POST'])
def flows_agent_compose_stream():
    from orchestration.flow_agent_service import stream_compose

    body = request.get_json(silent=True) or {}
    message = body.get('message') or body.get('description') or ''
    flow_id = body.get('flow_id')
    history = body.get('history')
    if not str(message).strip():
        return jsonify({'success': False, 'error': '缺少 message'}), 400

    def generate():
        try:
            for ev in stream_compose(message, flow_id=flow_id, history=history):
                yield f'data: {_json.dumps(ev, ensure_ascii=False)}\n\n'
        except Exception as exc:  # noqa: BLE001
            yield f'data: {_json.dumps({"type": "error", "error": str(exc)}, ensure_ascii=False)}\n\n'

    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'Connection': 'keep-alive',
        },
    )


@tools_bp.route('/flows/agent/validate', methods=['POST'])
def flows_agent_validate():
    from orchestration.flow_agent_service import validate_yaml_text

    body = request.get_json(silent=True) or {}
    yaml_text = body.get('yaml') or body.get('text') or ''
    if not str(yaml_text).strip():
        return jsonify({'success': False, 'error': '缺少 yaml'}), 400
    data = validate_yaml_text(yaml_text)
    return jsonify({'success': True, 'data': data})


@tools_bp.route('/flows/agent/save', methods=['POST'])
def flows_agent_save():
    from orchestration.flow_agent_service import save_flow_yaml

    body = request.get_json(silent=True) or {}
    yaml_text = body.get('yaml') or body.get('text') or ''
    overwrite = bool(body.get('overwrite'))
    if not str(yaml_text).strip():
        return jsonify({'success': False, 'error': '缺少 yaml'}), 400
    try:
        data = save_flow_yaml(yaml_text, overwrite=overwrite)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    ok = data.get('success', False)
    code = 200 if ok else (409 if data.get('exists') else 400)
    return jsonify({'success': ok, 'data': data, 'error': data.get('error')}), code


@tools_bp.route('/flows/agent/preview-graph', methods=['POST'])
def flows_agent_preview_graph():
    from orchestration.flow_agent_service import preview_graph_from_yaml

    body = request.get_json(silent=True) or {}
    yaml_text = body.get('yaml') or body.get('text') or ''
    if not str(yaml_text).strip():
        return jsonify({'success': False, 'error': '缺少 yaml'}), 400
    try:
        data = preview_graph_from_yaml(yaml_text)
    except Exception as exc:  # noqa: BLE001
        return jsonify({'success': False, 'error': str(exc)}), 500
    ok = data.get('success', False)
    return jsonify({'success': ok, 'data': data}), (200 if ok else 400)


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
