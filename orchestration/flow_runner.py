"""本地 Flow 执行器（Catalog Pipeline YAML → 顺序 invoke 工具）。"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from capabilities.base import CapabilityResult, RunContext
from orchestration.loader import discover_pipelines, load_pipeline_yaml, validate_pipeline

_TEMPLATE_RE = re.compile(r'\{\{([^}]+)\}\}')


@dataclass
class FlowStepResult:
    step_id: str
    tool: str
    status: str
    params: dict = field(default_factory=dict)
    outputs: dict = field(default_factory=dict)
    reason: str | None = None


@dataclass
class FlowRunResult:
    flow_id: str
    run_id: str
    status: str
    params: dict = field(default_factory=dict)
    steps: list[FlowStepResult] = field(default_factory=list)
    pause_at: str | None = None
    reason: str | None = None

    def to_dict(self) -> dict:
        return {
            'flow_id': self.flow_id,
            'run_id': self.run_id,
            'status': self.status,
            'params': self.params,
            'pause_at': self.pause_at,
            'reason': self.reason,
            'steps': [
                {
                    'step_id': s.step_id,
                    'tool': s.tool,
                    'status': s.status,
                    'params': s.params,
                    'outputs': s.outputs,
                    'reason': s.reason,
                }
                for s in self.steps
            ],
        }


def _get_path(obj: dict, path: str) -> Any:
    cur: Any = obj
    for part in path.split('.'):
        if not part:
            continue
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def resolve_templates(value: Any, params: dict, steps: dict) -> Any:
    if isinstance(value, dict):
        return {k: resolve_templates(v, params, steps) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_templates(v, params, steps) for v in value]
    if not isinstance(value, str):
        return value

    matches = list(_TEMPLATE_RE.finditer(value))
    if not matches:
        return value
    if len(matches) == 1 and matches[0].group(0) == value.strip():
        return _resolve_path(matches[0].group(1).strip(), params, steps)

    out = value
    for m in matches:
        resolved = _resolve_path(m.group(1).strip(), params, steps)
        out = out.replace(m.group(0), '' if resolved is None else str(resolved))
    return out


def _resolve_path(path: str, params: dict, steps: dict) -> Any:
    if path.startswith('params.'):
        return _get_path(params, path[7:])
    if path.startswith('steps.'):
        return _get_path(steps, path[6:])
    return None


def _topo_order(nodes: list[dict]) -> list[dict]:
    by_id = {n['id']: n for n in nodes if n.get('id')}
    indeg = {nid: 0 for nid in by_id}
    for n in nodes:
        for req in n.get('requires') or []:
            if req in indeg:
                indeg[n['id']] += 1
    ready = [nid for nid, d in indeg.items() if d == 0]
    order: list[str] = []
    while ready:
        nid = ready.pop(0)
        order.append(nid)
        for n in nodes:
            if nid in (n.get('requires') or []):
                indeg[n['id']] -= 1
                if indeg[n['id']] == 0:
                    ready.append(n['id'])
    if len(order) != len(by_id):
        raise ValueError('Pipeline 存在循环依赖或未满足的 requires')
    return [by_id[nid] for nid in order]


def find_pipeline(flow_id_or_path: str) -> tuple[dict, str]:
    path = flow_id_or_path
    if not path.endswith(('.yaml', '.yml')):
        for p in discover_pipelines():
            if p.get('id') == flow_id_or_path:
                path = p.get('_path') or ''
                break
    if not path or not __import__('os').path.isfile(path):
        raise FileNotFoundError(f'未找到 Flow: {flow_id_or_path}')
    defn = load_pipeline_yaml(path)
    defn['_path'] = path
    return defn, path


def run_flow(
    defn: dict,
    params: dict | None = None,
    *,
    auto_resume: bool = False,
    run_id: str | None = None,
) -> FlowRunResult:
    from capabilities.registry import init_registry

    errors = validate_pipeline(defn)
    if errors:
        raise ValueError('Pipeline 校验失败: ' + '; '.join(errors))

    reg = init_registry()
    flow_id = str(defn.get('id') or 'flow')
    run_id = run_id or f'run-{uuid.uuid4().hex[:10]}'
    flow_params = dict(params or {})
    step_outputs: dict[str, dict] = {}
    step_results: list[FlowStepResult] = []

    for node in _topo_order(defn.get('nodes') or []):
        step_id = node['id']
        tool = node.get('tool') or node.get('kind')
        resolved_params = resolve_templates(node.get('params') or {}, flow_params, step_outputs)
        ctx = RunContext(
            run_id=run_id,
            step_id=step_id,
            params=resolved_params,
            inputs={'steps': step_outputs},
        )
        try:
            result = reg.execute(tool, ctx)
        except Exception as e:
            fr = FlowStepResult(step_id, tool, 'failed', resolved_params, reason=str(e))
            step_results.append(fr)
            return FlowRunResult(
                flow_id=flow_id,
                run_id=run_id,
                status='failed',
                params=flow_params,
                steps=step_results,
                reason=str(e),
            )

        if result.status == 'waiting_human' and auto_resume:
            merged = dict(result.outputs)
            merged['waiting'] = False
            merged['auto_resumed'] = True
            merged['approved_by'] = 'demo-auto-resume'
            result = CapabilityResult(status='done', outputs=merged)

        fr = FlowStepResult(
            step_id=step_id,
            tool=tool,
            status=result.status,
            params=resolved_params,
            outputs=dict(result.outputs),
            reason=result.reason,
        )
        step_results.append(fr)
        step_outputs[step_id] = dict(result.outputs)

        if result.status == 'waiting_human':
            return FlowRunResult(
                flow_id=flow_id,
                run_id=run_id,
                status='waiting_human',
                params=flow_params,
                steps=step_results,
                pause_at=step_id,
                reason=result.reason or '等待人工确认',
            )
        if result.status == 'failed':
            return FlowRunResult(
                flow_id=flow_id,
                run_id=run_id,
                status='failed',
                params=flow_params,
                steps=step_results,
                reason=result.reason,
            )

    return FlowRunResult(
        flow_id=flow_id,
        run_id=run_id,
        status='done',
        params=flow_params,
        steps=step_results,
    )
