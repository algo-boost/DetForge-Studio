/** 工作流 DAG 编辑：预设、编译、布局 */

import { schemaForPreset as catalogSchemaForPreset } from './workflowCatalog';
import { FLOW_NODE_H, FLOW_NODE_W } from './workflowFlowGeometry';

export { schemaForPreset } from './workflowCatalog';

export const WF_STEP_DRAG_MIME = 'application/x-iisp-wf-step';

export const EDGE_WHEN = [
  { value: 'always', label: '始终' },
  { value: 'on_success', label: '成功时' },
  { value: 'on_empty', label: '结果为空' },
  { value: 'on_error', label: '失败时' },
];

const KINDS = [
  'query', 'predict', 'curation-create', 'curation-export',
  'gate-human', 'curation-import', 'curation-archive', 'notify',
];

let nodeSeq = 0;

export function resetNodeSeq() {
  nodeSeq = 0;
}

export function newNodeId(kind) {
  nodeSeq += 1;
  const base = String(kind || 'step').replace(/[^a-z0-9_-]/gi, '_');
  return `${base}_${nodeSeq}`;
}

export function listStepKinds() {
  return KINDS;
}

function linearGraph(stepKinds, y = 120) {
  const nodes = stepKinds.map((kind, i) => ({
    id: kind.replace(/-/g, '_'),
    kind,
    params: defaultNodeParams(kind),
    position: { x: 80 + i * 240, y },
  }));
  const edges = [];
  for (let i = 1; i < nodes.length; i += 1) {
    edges.push({ from: nodes[i - 1].id, to: nodes[i].id, when: 'always' });
  }
  return { nodes, edges };
}

export function graphPreset(presetId) {
  resetNodeSeq();
  if (presetId === 'daily_ng_curation') {
    return linearGraph([
      'query', 'curation-create', 'curation-export', 'gate-human',
      'curation-import', 'curation-archive', 'notify',
    ]);
  }
  if (presetId === 'weekly_predict_eval') {
    return linearGraph(['query', 'predict', 'notify']);
  }
  if (presetId === 'branch_empty_notify') {
    return {
      nodes: [
        { id: 'query', kind: 'query', params: {}, position: { x: 80, y: 120 } },
        { id: 'notify', kind: 'notify', params: { event: 'workflow_done' }, position: { x: 320, y: 120 } },
      ],
      edges: [
        { from: 'query', to: 'notify', when: 'on_empty' },
      ],
    };
  }
  return { nodes: [], edges: [] };
}

export function defaultNodeParams(kind, upstreamKind, upstreamId) {
  const k = String(kind || '');
  if (k === 'curation-create') {
    return { task_id: upstreamId ? `{{steps.${upstreamId}.task_id}}` : '' };
  }
  if (k === 'curation-export' || k === 'gate-human' || k === 'curation-import' || k === 'curation-archive') {
    return { batch_id: upstreamId ? `{{steps.${upstreamId}.batch_id}}` : '' };
  }
  if (k === 'predict') {
    return { task_id: upstreamId ? `{{steps.${upstreamId}.task_id}}` : '' };
  }
  if (k === 'notify') {
    return { event: 'workflow_done' };
  }
  return {};
}

export function autoLayout(nodes, index) {
  return { x: 80 + index * 240, y: 120 + (index % 2) * 100 };
}

export function inferParamsSchema(nodes = []) {
  const hasPredict = nodes.some((n) => n.kind === 'predict');
  const hasQuery = nodes.some((n) => n.kind === 'query');
  const schema = {};
  if (hasQuery) {
    schema.strategy_id = { type: 'strategy', default: 'daily_trawl', label: '策略' };
    schema.time_window = { type: 'time_window', default: { preset: 'yesterday' }, label: '时间窗' };
  }
  if (hasPredict) {
    schema.model_id = { type: 'model', label: '模型' };
  }
  if (nodes.some((n) => n.kind === 'gate-human')) {
    schema.reviewer = { type: 'string', label: '复核人' };
  }
  return schema;
}

export function compileGraphDefinition(graph, schema) {
  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const incoming = new Map(nodes.map((n) => [n.id, []]));
  for (const e of edges) {
    if (incoming.has(e.to)) incoming.get(e.to).push(e);
  }
  const steps = nodes.map((n) => {
    const reqs = (incoming.get(n.id) || [])
      .filter((e) => !e.when || e.when === 'always' || e.when === 'on_success')
      .map((e) => e.from);
    const step = { id: n.id, kind: n.kind, params: n.params || {} };
    if (reqs.length) step.requires = [...new Set(reqs)];
    return step;
  });
  return {
    params_schema: schema || inferParamsSchema(nodes),
    steps,
    edges,
  };
}

export function graphFromLinearSteps(steps = []) {
  const nodes = steps.map((s, i) => ({
    id: s.id,
    kind: s.kind,
    params: s.params || {},
    position: { x: 80 + i * 220, y: 120 },
  }));
  const edges = [];
  for (let i = 1; i < nodes.length; i += 1) {
    edges.push({ from: nodes[i - 1].id, to: nodes[i].id, when: 'always' });
  }
  return { nodes, edges };
}

export function schemaForPresetFromCatalog(id) {
  return catalogSchemaForPreset(id);
}
