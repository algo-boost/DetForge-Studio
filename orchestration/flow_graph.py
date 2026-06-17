"""Legacy / workflow Flow → 只读流程图（节点 + 工具 manifest）。"""
from __future__ import annotations

from typing import Any


def extract_legacy_flow_graph(defn: dict) -> dict[str, Any]:
    nodes: list[dict] = []
    edges: list[dict] = []
    prev: str | None = None
    for item in defn.get('nodes') or defn.get('steps') or []:
        if not isinstance(item, dict):
            continue
        nid = str(item.get('id') or '').strip()
        if not nid:
            continue
        tool_id = str(item.get('tool') or item.get('kind') or nid)
        entry = {
            'id': nid,
            'tool_id': tool_id,
            'kind': tool_id,
            'task_type': 'legacy',
            'node_kind': 'tool',
            'branch': 'main',
            'description': item.get('description'),
            'params_preview': item.get('params') or {},
        }
        nodes.append(entry)
        if prev:
            edges.append({'from': prev, 'to': nid, 'branch': 'main'})
        prev = nid
    return {'nodes': nodes, 'edges': edges}


def enrich_graph_with_tools(graph: dict) -> dict[str, Any]:
    from capabilities import get_registry

    reg = get_registry()
    tools_by_id = {t['id']: t for t in reg.list_tools()}
    enriched_nodes = []
    for node in graph.get('nodes') or []:
        copy = dict(node)
        tid = copy.get('tool_id')
        tool = tools_by_id.get(tid) if tid else None
        if tool:
            copy['tool'] = {
                'id': tool['id'],
                'label': tool.get('label') or tid,
                'description': tool.get('description') or '',
                'inputs': tool.get('inputs') or [],
                'outputs': tool.get('outputs') or [],
                'params_schema': tool.get('params_schema') or {},
                'artifacts': tool.get('artifacts') or [],
            }
        enriched_nodes.append(copy)
    return {**graph, 'nodes': enriched_nodes}


def build_flow_graph(
    defn: dict,
    *,
    engine: str = 'legacy',
    yaml_text: str | None = None,
) -> dict[str, Any]:
    graph = extract_legacy_flow_graph(defn)
    graph['engine'] = engine
    graph['flow_id'] = defn.get('id')
    graph = enrich_graph_with_tools(graph)
    if yaml_text:
        from orchestration.flow_readable import enrich_graph_readable
        graph = enrich_graph_readable(graph, yaml_text=yaml_text, flow_defn=defn)
    return graph


def _duration_seconds(started: str | None, ended: str | None) -> float | None:
    if not started or not ended:
        return None
    from datetime import datetime

    def _parse(value: str):
        try:
            return datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return None

    a, b = _parse(started), _parse(ended)
    if a and b:
        delta = (b - a).total_seconds()
        return round(delta, 3) if delta >= 0 else None
    return None


def merge_run_status(graph: dict, steps: list[dict]) -> dict[str, Any]:
    """将运行步骤状态、I/O、耗时合并到图节点。"""
    from orchestration.flow_readable import apply_run_io_to_readable

    by_id = {str(s.get('step_id') or ''): s for s in (steps or [])}
    nodes = []
    for node in graph.get('nodes') or []:
        copy = dict(node)
        step = by_id.get(copy.get('id') or '')
        if step:
            io = step.get('io') or {}
            copy['status'] = step.get('status')
            copy['io'] = step.get('io')
            copy['error'] = step.get('error')
            copy['started_at'] = step.get('started_at')
            copy['ended_at'] = step.get('ended_at')
            copy['duration_seconds'] = _duration_seconds(
                step.get('started_at'), step.get('ended_at'),
            )
            copy['run_detail'] = {
                'status': step.get('status'),
                'tool_status': io.get('status') if isinstance(io, dict) else None,
                'http_code': io.get('http_code') if isinstance(io, dict) else None,
                'reason': io.get('reason') if isinstance(io, dict) else None,
                'outputs': io.get('outputs') if isinstance(io, dict) else None,
                'artifacts': io.get('artifacts') if isinstance(io, dict) else None,
                'raw': (io.get('raw_body') or io.get('raw_outputs')) if isinstance(io, dict) else None,
                'started_at': step.get('started_at'),
                'ended_at': step.get('ended_at'),
                'error': step.get('error'),
            }
            if copy.get('readable'):
                copy['readable'] = apply_run_io_to_readable(dict(copy['readable']), copy.get('io'))
        nodes.append(copy)
    return {**graph, 'nodes': nodes}
