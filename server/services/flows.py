"""Flow Catalog 与运行记录聚合（U3）。"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from orchestration.loader import discover_kestra_flows, discover_pipelines, load_pipeline_yaml
from orchestration.flow_runner import find_pipeline
from server.services import workbench as wb
from studio.paths import APP_ROOT


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    return str(value)


def encode_run_key(source: str, run_id: str) -> str:
    return f'{source}:{run_id}'


def decode_run_key(run_key: str) -> tuple[str, str]:
    if ':' not in run_key:
        raise ValueError(f'无效 run_key: {run_key}')
    source, run_id = run_key.split(':', 1)
    if source not in ('demo', 'workflow', 'kestra'):
        raise ValueError(f'未知 source: {source}')
    return source, run_id


def _releases_path() -> str:
    for root in (
        os.path.join(APP_ROOT, 'catalog_cache', 'repo'),
        os.path.join(APP_ROOT, 'iisp-catalog'),
    ):
        path = os.path.join(root, 'releases.yaml')
        if os.path.isfile(path):
            return path
    return os.path.join(APP_ROOT, 'iisp-catalog', 'releases.yaml')


def list_releases() -> list[dict]:
    path = _releases_path()
    if not os.path.isfile(path):
        return []
    try:
        import yaml
    except ImportError:
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    releases = data.get('releases') or {}
    rows = []
    for version, meta in releases.items():
        if not isinstance(meta, dict):
            continue
        rows.append({
            'version': version,
            'published_at': meta.get('published_at'),
            'status': meta.get('status') or 'draft',
            'note': meta.get('note') or '',
            'pipelines': meta.get('pipelines') or [],
            'strategies': meta.get('strategies') or [],
        })
    rows.sort(key=lambda r: str(r.get('version') or ''), reverse=True)
    return rows


def _release_map() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for rel in list_releases():
        for pipe in rel.get('pipelines') or []:
            pid = pipe.get('id')
            if pid and pid not in out:
                out[pid] = {
                    'release_version': rel.get('version'),
                    'release_status': rel.get('status'),
                    'catalog_version': pipe.get('version'),
                    'catalog_path': pipe.get('path'),
                }
    return out


def _find_kestra_flow(flow_id: str) -> tuple[dict, dict] | None:
    """返回 (flow_yaml, discover_meta)。"""
    fid = str(flow_id or '').strip()
    if not fid:
        return None
    for meta in discover_kestra_flows():
        if str(meta.get('id') or '') != fid:
            continue
        path = meta.get('_path')
        if not path:
            return None
        try:
            data = load_pipeline_yaml(path)
        except Exception:
            return None
        return data, meta
    return None


def list_flow_catalog() -> list[dict]:
    """Kestra + legacy/demo pipelines，附 release 元数据。"""
    from orchestration import kestra_client as kc
    from orchestration.kestra_inputs import extract_kestra_task_outline, parse_kestra_inputs

    kestra_ok = kc.is_enabled()
    release_by_id = _release_map()
    seen: set[str] = set()
    rows: list[dict] = []

    for flow in discover_kestra_flows():
        fid = str(flow.get('id') or '')
        if not fid or fid in seen:
            continue
        seen.add(fid)
        rel = release_by_id.get(fid, {})
        params_schema: dict = {}
        nodes: list[dict] = []
        valid = flow.get('_valid', True)
        path = flow.get('_path')
        if path and valid:
            try:
                data = load_pipeline_yaml(path)
                params_schema = parse_kestra_inputs(data)
                nodes = extract_kestra_task_outline(data)
            except Exception:
                valid = False
        rows.append({
            'id': fid,
            'label': fid,
            'engine': 'kestra',
            'description': flow.get('description') or '',
            'namespace': flow.get('namespace') or 'iisp',
            'path': path,
            'valid': valid,
            'runnable': bool(valid and kestra_ok),
            'kestra_enabled': kestra_ok,
            'params_schema': params_schema,
            'nodes': nodes,
            **rel,
        })

    for pipe in discover_pipelines():
        if pipe.get('tasks'):
            continue
        fid = str(pipe.get('id') or '')
        if not fid or fid in seen:
            continue
        seen.add(fid)
        rel = release_by_id.get(fid, {})
        nodes = pipe.get('nodes') or pipe.get('steps') or []
        rows.append({
            'id': fid,
            'label': pipe.get('name') or fid,
            'engine': 'legacy',
            'description': pipe.get('description') or '',
            'namespace': 'iisp',
            'path': pipe.get('_path'),
            'valid': pipe.get('_valid', True),
            'runnable': bool(nodes) and pipe.get('_valid', True),
            'params_schema': pipe.get('params_schema') or pipe.get('params') or {},
            'nodes': [{'id': n.get('id'), 'tool': n.get('tool') or n.get('kind')} for n in nodes],
            **rel,
        })

    return sorted(rows, key=lambda r: str(r.get('id') or ''))


def execute_kestra_flow(
    flow_id: str,
    *,
    namespace: str | None = None,
    inputs: dict | None = None,
) -> dict:
    from orchestration import kestra_client as kc
    from orchestration.kestra_inputs import (
        apply_input_defaults,
        normalize_execution_inputs,
        parse_kestra_inputs,
    )

    if not kc.is_enabled():
        raise RuntimeError('Kestra 未启用（设置 KESTRA_ENABLED=1 并启动 Kestra 服务）')

    found = _find_kestra_flow(flow_id)
    if not found:
        raise FileNotFoundError(f'Kestra Flow 未找到: {flow_id}')
    flow_data, meta = found
    ns = str(namespace or meta.get('namespace') or flow_data.get('namespace') or 'iisp')
    params_schema = parse_kestra_inputs(flow_data)
    merged = apply_input_defaults(inputs, params_schema)
    payload = normalize_execution_inputs(merged, params_schema)

    result = kc.execute_flow(flow_id, namespace=ns, inputs=payload or None)
    execution_id = str(result.get('execution_id') or '')
    if not execution_id:
        raise RuntimeError('Kestra 未返回 execution_id')

    state = str(result.get('state') or '').upper()
    status = 'waiting_human' if state == 'PAUSED' else _map_kestra_state(state.lower())
    run_key = encode_run_key('kestra', execution_id)
    return {
        'run_key': run_key,
        'run_id': execution_id,
        'execution_id': execution_id,
        'source': 'kestra',
        'flow_id': flow_id,
        'namespace': ns,
        'status': status,
        'kestra_url': result.get('kestra_url'),
        'inputs': payload,
    }


def get_pipeline_yaml(flow_id: str) -> dict:
    defn, path = find_pipeline(flow_id)
    with open(path, 'r', encoding='utf-8') as f:
        yaml_text = f.read()
    return {
        'id': defn.get('id') or flow_id,
        'path': path,
        'yaml': yaml_text,
        'definition': defn,
    }


def get_flow_graph(flow_id: str) -> dict:
    """只读流程图：节点 + 工具 manifest + 可读化入参/出参表单。"""
    from orchestration.kestra_graph import build_flow_graph

    found = _find_kestra_flow(flow_id)
    if found:
        data, meta = found
        yaml_text = ''
        path = meta.get('_path')
        if path and os.path.isfile(path):
            with open(path, 'r', encoding='utf-8') as f:
                yaml_text = f.read()
        graph = build_flow_graph(data, engine='kestra', yaml_text=yaml_text or None)
        graph['path'] = path
        return graph
    try:
        defn, path = find_pipeline(flow_id)
    except FileNotFoundError:
        raise FileNotFoundError(f'Flow 未找到: {flow_id}') from None
    yaml_text = ''
    if path and os.path.isfile(path):
        with open(path, 'r', encoding='utf-8') as f:
            yaml_text = f.read()
    graph = build_flow_graph(defn, engine='legacy', yaml_text=yaml_text or None)
    graph['path'] = path
    return graph


def list_flow_runs(
    *,
    status: str | None = None,
    flow_id: str | None = None,
    limit: int = 50,
) -> list[dict]:
    rows: list[dict] = []

    for run in wb.collect_workflow_runs(status=status, limit=limit):
        run_id = str(run.get('id'))
        rows.append({
            'run_key': encode_run_key('workflow', run_id),
            'source': 'workflow',
            'run_id': run_id,
            'flow_id': run.get('template_id'),
            'name': run.get('name') or f'Run #{run_id}',
            'status': run.get('status'),
            'created_at': _iso(run.get('created_at') or run.get('started_at')),
        })

    for row in wb.collect_demo_flow_runs(status=status)[:limit]:
        run_id = row['run_id']
        defn = (row.get('_pending') or {}).get('defn') or {}
        rows.append({
            'run_key': encode_run_key('demo', run_id),
            'source': 'demo',
            'run_id': run_id,
            'flow_id': row.get('flow_id') or defn.get('id'),
            'name': defn.get('name') or row.get('flow_id') or run_id,
            'status': row.get('status'),
            'created_at': None,
            'pause_at': row.get('pause_at'),
        })

    if status in (None, 'waiting_human'):
        for ex in wb.collect_kestra_paused(limit=limit):
            exec_id = str(ex.get('execution_id') or '')
            if not exec_id:
                continue
            rows.append({
                'run_key': encode_run_key('kestra', exec_id),
                'source': 'kestra',
                'run_id': exec_id,
                'flow_id': ex.get('flow_id'),
                'name': ex.get('flow_id') or exec_id,
                'status': 'waiting_human',
                'created_at': ex.get('started_at'),
                'batch_id': ex.get('batch_id'),
                'kestra_url': ex.get('kestra_url'),
            })

    if status:
        rows = [r for r in rows if r.get('status') == status]
    if flow_id:
        fid = str(flow_id).strip()
        rows = [r for r in rows if str(r.get('flow_id') or '') == fid]
    return rows[:limit]


def get_flow_run(run_key: str) -> dict | None:
    try:
        source, run_id = decode_run_key(run_key)
    except ValueError:
        return None

    if source == 'demo':
        from server.routes.tools import _demo_flow_runs

        pending = _demo_flow_runs.get(run_id)
        if not pending:
            return None
        defn = pending.get('defn') or {}
        steps = _normalize_demo_steps(pending.get('steps') or [])
        last_status = steps[-1].get('status') if steps else 'waiting_human'
        status = 'waiting_human' if pending.get('pause_at') else last_status
        flow_id = defn.get('id')
        graph = None
        if flow_id:
            try:
                from orchestration.kestra_graph import merge_run_status
                graph = merge_run_status(get_flow_graph(flow_id), steps)
            except Exception:
                graph = None
        return {
            'run_key': run_key,
            'source': 'demo',
            'run_id': run_id,
            'flow_id': flow_id,
            'name': defn.get('name') or defn.get('id'),
            'status': status,
            'pause_at': pending.get('pause_at'),
            'params': pending.get('params') or {},
            'steps': steps,
            'graph': graph,
            'flow_path': None,
        }

    if source == 'workflow':
        try:
            from studio.forge.workflow_engine import get_run_detail

            detail = get_run_detail(int(run_id))
            run = detail['run']
            steps = detail.get('steps') or []
            gate = next((s for s in steps if s.get('status') == 'waiting_human'), None)
            return {
                'run_key': run_key,
                'source': 'workflow',
                'run_id': str(run_id),
                'flow_id': run.get('template_id'),
                'name': run.get('name') or f'Run #{run_id}',
                'status': run.get('status'),
                'created_at': _iso(run.get('created_at')),
                'params': run.get('params') or {},
                'steps': [
                    {
                        'step_id': s.get('step_id'),
                        'tool': s.get('kind'),
                        'status': s.get('status'),
                        'output': s.get('output'),
                        'io': {'outputs': s.get('output')} if s.get('output') else None,
                        'error': s.get('error'),
                        'human_action': s.get('human_action'),
                        'child_batch_id': s.get('child_batch_id'),
                    }
                    for s in steps
                ],
                'gate_step': gate,
                'batch_id': (gate or {}).get('child_batch_id')
                or ((gate or {}).get('human_action') or {}).get('batch_id'),
                'template': detail.get('template'),
                'notifications': detail.get('notifications') or [],
            }
        except Exception:
            return None

    if source == 'kestra':
        if not wb._kestra_enabled():
            return None
        try:
            from orchestration import kestra_client as kc
            from orchestration.kestra_graph import merge_run_status

            ex = kc.get_execution(run_id)
            summary = kc.summarize_execution(ex)
            state = str(summary.get('state') or '').lower()
            steps = _kestra_task_run_steps(ex)
            flow_id = summary.get('flow_id')
            graph = None
            if flow_id:
                try:
                    graph = merge_run_status(get_flow_graph(flow_id), steps)
                except Exception:
                    graph = None
            return {
                'run_key': run_key,
                'source': 'kestra',
                'run_id': run_id,
                'flow_id': flow_id,
                'name': flow_id or run_id,
                'status': 'waiting_human' if state == 'paused' else _map_kestra_state(state),
                'batch_id': summary.get('batch_id'),
                'kestra_url': summary.get('kestra_url'),
                'inputs': (ex.get('inputs') or {}),
                'steps': steps,
                'graph': graph,
                'raw': ex,
            }
        except Exception:
            return None

    return None


def _kestra_task_run_steps(execution: dict) -> list[dict]:
    rows = []
    for tr in (execution or {}).get('taskRunList') or []:
        state = ((tr.get('state') or {}).get('current') or '').lower()
        task_id = tr.get('taskId') or tr.get('id') or 'task'
        rows.append({
            'step_id': task_id,
            'tool': task_id,
            'status': _map_kestra_state(state),
            'io': _parse_kestra_task_io(tr),
            'error': ((tr.get('state') or {}).get('message') or None),
            'started_at': _iso((tr.get('state') or {}).get('startDate')),
            'ended_at': _iso((tr.get('state') or {}).get('endDate')),
        })
    return rows


def _normalize_demo_steps(steps: list) -> list[dict]:
    rows = []
    for s in steps or []:
        if not isinstance(s, dict):
            continue
        outputs = s.get('outputs') or s.get('output')
        rows.append({
            'step_id': s.get('step_id'),
            'tool': s.get('tool') or s.get('kind'),
            'status': s.get('status'),
            'io': {'outputs': outputs} if outputs else (s.get('io') or None),
            'error': s.get('error'),
        })
    return rows


def _parse_kestra_task_io(task_run: dict) -> dict:
    """解析 Kestra 单步 outputs → IISP invoke 风格 I/O。"""
    import json

    outputs = task_run.get('outputs') or {}
    if not outputs:
        return {}

    body = outputs.get('body')
    if body is None:
        return {'raw_outputs': outputs}

    try:
        payload = json.loads(body) if isinstance(body, str) else body
    except (TypeError, ValueError):
        return {'raw_outputs': outputs, 'body': body}

    if not isinstance(payload, dict):
        return {'raw_outputs': outputs, 'body': payload}

    return {
        'status': payload.get('status'),
        'outputs': payload.get('outputs'),
        'artifacts': payload.get('artifacts'),
        'reason': payload.get('reason'),
        'http_code': outputs.get('code'),
        'raw_body': payload,
    }


def _map_kestra_state(state: str) -> str:
    mapping = {
        'success': 'done',
        'running': 'running',
        'paused': 'waiting_human',
        'failed': 'failed',
        'killed': 'canceled',
        'warning': 'done',
    }
    return mapping.get(state, state or 'pending')


def resume_flow_run(run_key: str, body: dict | None = None) -> dict:
    body = body or {}
    source, run_id = decode_run_key(run_key)

    if source == 'workflow':
        from studio.forge.workflow_engine import resume_run

        run = resume_run(int(run_id))
        return {
            'run_key': run_key,
            'status': (run or {}).get('status') or 'running',
            'run_id': run_id,
        }

    if source == 'demo':
        from server.routes.tools import resume_demo_flow

        payload = resume_demo_flow(run_id, approved_by=body.get('approved_by') or 'web-user')
        return {
            'run_key': run_key,
            'status': payload.get('status') or 'done',
            'data': payload.get('data'),
        }

    if source == 'kestra':
        from orchestration import kestra_client as kc

        inputs = body.get('inputs') if isinstance(body.get('inputs'), dict) else None
        data = kc.resume_execution(run_id, inputs=inputs)
        return {'run_key': run_key, 'status': 'running', 'data': data}

    raise ValueError(f'未知 source: {source}')
