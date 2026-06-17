"""Flow Catalog 与运行记录聚合（U3）。"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from orchestration.loader import discover_pipelines
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
    if source not in ('demo', 'workflow'):
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


def list_flow_catalog() -> list[dict]:
    """legacy/demo pipelines + 组合编排模板，附 release 元数据。"""
    release_by_id = _release_map()
    seen: set[str] = set()
    rows: list[dict] = []

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

    for row in _list_forge_compose_templates():
        fid = str(row.get('id') or '')
        if fid and fid not in seen:
            seen.add(fid)
            rows.append(row)

    return sorted(rows, key=lambda r: str(r.get('id') or ''))


def _list_forge_compose_templates() -> list[dict]:
    """组合编排保存的 flow_* / custom_* 模板（只读展示，从组合编排页运行）。"""
    rows: list[dict] = []
    try:
        from studio.forge import forge_db
        if not forge_db.schema_ready():
            return rows
        for tpl in forge_db.list_workflow_templates(enabled_only=True):
            tid = str(tpl.get('id') or '')
            defn = tpl.get('definition') or {}
            if not (tid.startswith('custom_') or tid.startswith('flow_') or defn.get('compose')):
                continue
            steps = defn.get('steps') or []
            rows.append({
                'id': tid,
                'label': tpl.get('name') or tid,
                'engine': 'workflow',
                'description': tpl.get('description') or '组合编排流水线',
                'namespace': None,
                'path': None,
                'valid': True,
                'runnable': tid.startswith('flow_'),
                'params_schema': defn.get('params_schema') or {},
                'nodes': [{'id': s.get('id'), 'tool': s.get('kind')} for s in steps],
            })
    except Exception:
        pass
    return rows


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


def _get_forge_workflow_template(flow_id: str) -> dict | None:
    try:
        from studio.forge import forge_db
        if not forge_db.schema_ready():
            return None
        return forge_db.get_workflow_template(str(flow_id).strip())
    except Exception:
        return None


def _build_workflow_template_graph(flow_id: str, definition: dict | None = None) -> dict:
    from orchestration.flow_graph import build_flow_graph

    if definition is None:
        template = _get_forge_workflow_template(flow_id)
        if not template:
            raise FileNotFoundError(f'Flow 未找到: {flow_id}')
        definition = template.get('definition') or {}
    defn = dict(definition)
    defn['id'] = flow_id
    graph = build_flow_graph(defn, engine='workflow')
    graph['flow_id'] = flow_id
    graph['engine'] = 'workflow'
    graph['path'] = None
    return graph


def _workflow_run_graph(template: dict | None, flow_id: str, steps: list[dict]) -> dict | None:
    if not template and not flow_id:
        return None
    try:
        from orchestration.flow_graph import merge_run_status

        defn = (template or {}).get('definition') or {}
        graph = _build_workflow_template_graph(flow_id, defn)
        return merge_run_status(graph, steps)
    except Exception:
        return None


def get_flow_graph(flow_id: str) -> dict:
    """只读流程图：节点 + 工具 manifest + 可读化入参/出参表单。"""
    from orchestration.flow_graph import build_flow_graph

    template = _get_forge_workflow_template(flow_id)
    if template:
        return _build_workflow_template_graph(flow_id, template.get('definition'))

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
                from orchestration.flow_graph import merge_run_status
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
            from studio.forge.workflow_engine import ensure_run_advance, get_run_detail

            rid = int(run_id)
            ensure_run_advance(rid)
            detail = get_run_detail(rid)
            run = detail['run']
            steps = detail.get('steps') or []
            gate = next((s for s in steps if s.get('status') == 'waiting_human'), None)
            step_rows = [
                {
                    'step_id': s.get('step_id'),
                    'tool': s.get('kind'),
                    'status': s.get('status'),
                    'output': s.get('output'),
                    'io': {'outputs': s.get('output')} if s.get('output') else None,
                    'error': s.get('error'),
                    'human_action': s.get('human_action'),
                    'child_batch_id': s.get('child_batch_id'),
                    'started_at': s.get('started_at'),
                    'ended_at': s.get('finished_at') or s.get('ended_at'),
                }
                for s in steps
            ]
            flow_id = run.get('template_id')
            template = detail.get('template')
            graph = _workflow_run_graph(template, flow_id, step_rows)
            return {
                'run_key': run_key,
                'source': 'workflow',
                'run_id': str(run_id),
                'flow_id': flow_id,
                'name': run.get('name') or f'Run #{run_id}',
                'status': run.get('status'),
                'created_at': _iso(run.get('created_at')),
                'params': run.get('params') or {},
                'steps': step_rows,
                'graph': graph,
                'gate_step': gate,
                'batch_id': (gate or {}).get('child_batch_id')
                or ((gate or {}).get('human_action') or {}).get('batch_id'),
                'template': template,
                'notifications': detail.get('notifications') or [],
            }
        except Exception:
            return None

    return None


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

    raise ValueError(f'未知 source: {source}')
