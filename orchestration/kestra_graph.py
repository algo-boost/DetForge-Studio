"""Kestra / Legacy Flow → 只读流程图（节点 + 工具 manifest）。"""
from __future__ import annotations

import re
from typing import Any

_TOOL_URI_RE = re.compile(r'/v1/tools/([^/]+)/invoke', re.I)


def parse_tool_id_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    match = _TOOL_URI_RE.search(str(uri))
    return match.group(1) if match else None


def _task_kind(task_type: str) -> str:
    t = str(task_type or '')
    if 'Pause' in t:
        return 'pause'
    if 'flow.If' in t:
        return 'branch'
    if 'flow.Switch' in t:
        return 'branch'
    if 'log.Log' in t:
        return 'log'
    if 'http.Request' in t:
        return 'tool'
    if 'flow.Sequential' in t or 'flow.Parallel' in t:
        return 'container'
    return 'task'


def _append_node(
    nodes: list[dict],
    edges: list[dict],
    prev_id: str | None,
    *,
    node_id: str,
    tool_id: str | None,
    task_type: str,
    branch: str = 'main',
    description: str | None = None,
    request_body: str | None = None,
) -> str:
    kind = _task_kind(task_type)
    if kind in ('container',):
        return prev_id
    if kind == 'log':
        tool_id = tool_id or 'log'

    entry = {
        'id': node_id,
        'tool_id': tool_id or node_id,
        'kind': tool_id or kind,
        'task_type': task_type,
        'node_kind': kind,
        'branch': branch,
        'description': description,
    }
    if request_body:
        entry['request_body_preview'] = _trim_preview(request_body, 800)
    nodes.append(entry)
    if prev_id:
        edges.append({'from': prev_id, 'to': node_id, 'branch': branch})
    return node_id


def _trim_preview(text: str, limit: int) -> str:
    s = str(text or '').strip()
    if len(s) <= limit:
        return s
    return s[:limit] + '…'


def extract_kestra_flow_graph(flow: dict) -> dict[str, Any]:
    """从 Kestra tasks 树提取线性主路径节点（If 的 then 分支）。"""
    nodes: list[dict] = []
    edges: list[dict] = []

    def walk(task_list: list | None, *, branch: str = 'main', prev: str | None = None) -> str | None:
        last = prev
        for task in task_list or []:
            if not isinstance(task, dict):
                continue
            tid = str(task.get('id') or '').strip()
            ttype = str(task.get('type') or '')
            kind = _task_kind(ttype)

            if kind == 'container':
                last = walk(task.get('tasks'), branch=branch, prev=last)
                continue

            if kind == 'branch':
                if tid:
                    last = _append_node(
                        nodes, edges, last,
                        node_id=tid,
                        tool_id='branch',
                        task_type=ttype,
                        branch=branch,
                        description=task.get('condition'),
                    )
                last = walk(task.get('then'), branch='then', prev=last)
                if task.get('else'):
                    walk(task.get('else'), branch='else', prev=last)
                continue

            tool_id = parse_tool_id_from_uri(task.get('uri'))
            if kind == 'pause':
                tool_id = 'gate-human'
            body = task.get('body')
            last = _append_node(
                nodes, edges, last,
                node_id=tid or f'node_{len(nodes)}',
                tool_id=tool_id,
                task_type=ttype,
                branch=branch,
                description=task.get('description'),
                request_body=body if kind == 'tool' else None,
            )

            for key in ('tasks', 'finally', 'errors'):
                child = task.get(key)
                if isinstance(child, list):
                    last = walk(child, branch=branch, prev=last)

            cases = task.get('cases')
            if isinstance(cases, dict):
                for case_name, case_tasks in cases.items():
                    if isinstance(case_tasks, list):
                        last = walk(case_tasks, branch=str(case_name), prev=last)

        return last

    walk(flow.get('tasks') or [])
    return {'nodes': nodes, 'edges': edges}


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
        prev = _append_node(
            nodes, edges, prev,
            node_id=nid,
            tool_id=tool_id,
            task_type='legacy',
            description=item.get('description'),
            request_body=None,
        )
        nodes[-1]['params_preview'] = item.get('params') or {}
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
    engine: str = 'kestra',
    yaml_text: str | None = None,
) -> dict[str, Any]:
    if engine == 'kestra':
        graph = extract_kestra_flow_graph(defn)
    else:
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
            # 执行结果摘要，供节点详情直接展示
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
