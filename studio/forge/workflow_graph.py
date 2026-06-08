"""工作流 DAG：图归一化、分支条件、可运行节点调度。"""
from __future__ import annotations

from studio.forge.workflow_steps import resolve_templates

TERMINAL_STATUSES = frozenset({'done', 'skipped', 'failed'})
ACTIVE_WHEN = frozenset({'always', 'done', 'not_empty', 'empty', 'skipped'})


def _is_empty_output(output):
    if not isinstance(output, dict):
        return False
    if output.get('skipped') and output.get('reason') == 'empty_result':
        return True
    for key in ('row_count', 'count'):
        if key in output:
            try:
                return int(output[key]) <= 0
            except (TypeError, ValueError):
                pass
    return False


def eval_edge_when(when, pred_status, pred_output):
    """判断边是否激活。pred_status: done|skipped|..."""
    w = str(when or 'always').strip().lower()
    st = str(pred_status or '').lower()
    out = pred_output or {}

    if st == 'skipped':
        if w == 'skipped':
            return True
        if w == 'empty':
            return out.get('reason') == 'empty_result'
        return False

    if st == 'done':
        if w in ('always', 'done'):
            return True
        if w == 'not_empty':
            return not _is_empty_output(out)
        if w == 'empty':
            return _is_empty_output(out)
        return False

    return False


def linear_steps_to_graph(steps):
    """将 v1 线性 steps 转为 graph。"""
    steps = list(steps or [])
    nodes = []
    edges = []
    id_set = set()
    for s in steps:
        nid = str(s['id'])
        id_set.add(nid)
        nodes.append({
            'id': nid,
            'kind': s['kind'],
            'params': s.get('params') or {},
            'position': s.get('position'),
        })
    for i, s in enumerate(steps):
        nid = str(s['id'])
        reqs = s.get('requires') or []
        if reqs:
            for req in reqs:
                if str(req) in id_set:
                    edges.append({'from': str(req), 'to': nid, 'when': 'always'})
        elif i > 0:
            edges.append({'from': str(steps[i - 1]['id']), 'to': nid, 'when': 'always'})
    return {'nodes': nodes, 'edges': edges}


def normalize_definition(definition):
    """统一为含 graph + steps（拓扑序）的 definition。"""
    definition = dict(definition or {})
    graph = definition.get('graph')
    if not graph:
        steps = definition.get('steps') or []
        if not steps:
            raise ValueError('definition 需要 graph 或 steps')
        graph = linear_steps_to_graph(steps)
    nodes = list(graph.get('nodes') or [])
    edges = list(graph.get('edges') or [])
    if not nodes:
        raise ValueError('graph.nodes 不能为空')

    node_by_id = {str(n['id']): n for n in nodes}
    for e in edges:
        if str(e.get('from')) not in node_by_id or str(e.get('to')) not in node_by_id:
            raise ValueError(f"边引用未知节点: {e}")

    steps = topological_steps(nodes, edges)
    out = dict(definition)
    out['version'] = definition.get('version') or (2 if graph else 1)
    out['graph'] = {'nodes': nodes, 'edges': edges}
    out['steps'] = steps
    return out


def topological_steps(nodes, edges):
    """拓扑排序得到 steps 列表（含 requires）。"""
    nodes = list(nodes)
    edges = list(edges)
    ids = [str(n['id']) for n in nodes]
    indeg = {i: 0 for i in ids}
    adj = {i: [] for i in ids}
    pred_map = {i: [] for i in ids}
    for e in edges:
        f, t = str(e['from']), str(e['to'])
        if f in indeg and t in indeg:
            indeg[t] += 1
            adj[f].append(t)
            pred_map[t].append(f)

    queue = [i for i in ids if indeg[i] == 0]
    order = []
    while queue:
        queue.sort()
        cur = queue.pop(0)
        order.append(cur)
        for nxt in adj[cur]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(ids):
        raise ValueError('工作流 graph 存在环，无法执行')

    node_by_id = {str(n['id']): n for n in nodes}
    steps = []
    for nid in order:
        n = node_by_id[nid]
        steps.append({
            'id': nid,
            'kind': n['kind'],
            'params': n.get('params') or {},
            'requires': list(dict.fromkeys(pred_map.get(nid) or [])),
            'position': n.get('position'),
        })
    return steps


def entry_node_ids(graph):
    nodes = {str(n['id']) for n in (graph.get('nodes') or [])}
    targets = {str(e['to']) for e in (graph.get('edges') or [])}
    entries = [n for n in nodes if n not in targets]
    return entries or list(nodes)


def incoming_by_from(graph, node_id):
    """按前驱分组的入边。"""
    groups = {}
    for e in graph.get('edges') or []:
        if str(e.get('to')) != str(node_id):
            continue
        f = str(e.get('from'))
        groups.setdefault(f, []).append(e)
    return groups


def outgoing_edges(graph, node_id):
    return [e for e in (graph.get('edges') or []) if str(e.get('from')) == str(node_id)]


def _step_maps(step_runs):
    by_id = {}
    status = {}
    output = {}
    for s in step_runs:
        sid = str(s['step_id'])
        by_id[sid] = s
        status[sid] = s.get('status')
        output[sid] = s.get('output') or {}
    return by_id, status, output


def predecessors_satisfied(graph, node_id, status, output):
    """所有前驱已结束，且每个前驱至少有一条激活入边。"""
    groups = incoming_by_from(graph, node_id)
    if not groups:
        return True
    for from_id, edge_list in groups.items():
        st = status.get(from_id)
        if st not in TERMINAL_STATUSES:
            return False
        if not any(eval_edge_when(e.get('when'), st, output.get(from_id)) for e in edge_list):
            return False
    return True


def find_runnable_nodes(graph, step_runs):
    """返回可执行的 pending 节点 id 列表（拓扑序）。"""
    _, status, output = _step_maps(step_runs)
    order = [s['id'] for s in topological_steps(graph['nodes'], graph['edges'])]
    runnable = []
    for nid in order:
        if status.get(nid) != 'pending':
            continue
        if predecessors_satisfied(graph, nid, status, output):
            runnable.append(nid)
    return runnable


def propagate_branch_skips(run_id, graph, step_runs, *, update_fn, now_fn):
    """将因分支未选中而不可达的 pending 节点标为 skipped。"""
    _, status, output = _step_maps(step_runs)

    reachable = set()
    queue = []
    for eid in entry_node_ids(graph):
        st = status.get(eid)
        if st in TERMINAL_STATUSES:
            queue.append(eid)
        elif st in ('pending', 'running', 'waiting_human'):
            reachable.add(eid)

    while queue:
        cur = queue.pop(0)
        reachable.add(cur)
        st = status.get(cur)
        out = output.get(cur) or {}
        if st not in TERMINAL_STATUSES:
            continue
        for e in outgoing_edges(graph, cur):
            if not eval_edge_when(e.get('when'), st, out):
                continue
            nxt = str(e['to'])
            if nxt not in reachable:
                reachable.add(nxt)
                queue.append(nxt)

    changed = False
    for s in step_runs:
        sid = str(s['step_id'])
        if s.get('status') != 'pending':
            continue
        if sid not in reachable:
            update_fn(
                run_id, sid,
                status='skipped',
                output={'skipped': True, 'reason': 'branch_not_taken'},
                finished_at=now_fn(),
            )
            status[sid] = 'skipped'
            output[sid] = {'skipped': True, 'reason': 'branch_not_taken'}
            changed = True
    return changed


def all_nodes_terminal(graph, step_runs):
    _, status, _ = _step_maps(step_runs)
    ids = {str(n['id']) for n in graph.get('nodes') or []}
    return all(status.get(i) in TERMINAL_STATUSES for i in ids)


def has_waiting_human(step_runs):
    return any(s.get('status') == 'waiting_human' for s in step_runs)


def resolve_node_params(node, context):
    return resolve_templates(node.get('params') or {}, context)


def graph_for_template(definition):
    norm = normalize_definition(definition)
    return norm['graph'], norm['steps']
