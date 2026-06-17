/** Flow IR 规范化（对齐 studio/flow/flow_schema.py） */

const CONTAINER_TYPES = new Set(['control.if', 'control.loop']);
const CONTAINER_BRANCHES = {
  'control.if': ['then', 'else'],
  'control.loop': ['body'],
};

function ensureContainer(node) {
  const t = node.type;
  if (t === 'control.if') {
    node.then = node.then || [];
    node.else = node.else || [];
  } else if (t === 'control.loop') {
    node.body = node.body || [];
    node.params = node.params || {};
    if ((node.params.loop_mode || 'rules') === 'rules') {
      node.params.rules = node.params.rules || [];
    }
  }
}

function prepareNode(node) {
  if (!node || !node.type) return node;
  const out = { ...node };
  out.id = out.id || '';
  out.params = out.params || {};
  if (CONTAINER_TYPES.has(out.type)) {
    ensureContainer(out);
    for (const branch of CONTAINER_BRANCHES[out.type]) {
      out[branch] = (out[branch] || []).map((child) => prepareNode({ ...child }));
    }
  }
  return out;
}

function prepareFlow(flow) {
  const f = flow || {};
  const nodes = (f.nodes || []).map((n) => prepareNode({ ...n }));
  return { version: 2, nodes };
}

function isRulesLoop(node) {
  if (node?.type !== 'control.loop') return false;
  if ((node.params?.loop_mode || 'rules') !== 'rules') return false;
  const body = node.body || [];
  const rules = node.params?.rules;
  return body.some((n) => n.type === 'builtin.filter_df_by_ext')
    || body.some((n) => n.type === 'builtin.remove_empty_ext_rows')
    || (Array.isArray(rules) && rules.length > 0);
}

function findRulesLoopNode(flow) {
  const nodes = flow?.nodes || (prepareFlow(flow).nodes || []);
  return nodes.find(isRulesLoop) || null;
}

const REMOVE_EMPTY_TYPE = 'builtin.remove_empty_ext_rows';

/** 在规则循环 body 中增删「移除空框行」节点 */
function syncRulesLoopRemoveEmpty(flow, enabled) {
  const f = prepareFlow(flow || { version: 2, nodes: [] });
  const loop = (f.nodes || []).find(isRulesLoop) || null;
  if (!loop) return f;
  const body = [...(loop.body || [])];
  const without = body.filter((n) => n.type !== REMOVE_EMPTY_TYPE);
  if (enabled) {
    const hasFilter = without.some((n) => n.type === 'builtin.filter_df_by_ext');
    if (!hasFilter) {
      without.unshift({
        id: 'f_filter',
        type: 'builtin.filter_df_by_ext',
        params: { bind_loop_rule: 'loop_rule' },
      });
    }
    without.push({ id: 'f_remove_empty', type: REMOVE_EMPTY_TYPE, params: {} });
  }
  loop.body = without;
  return f;
}

/** 从策略字段 / flow / 编译代码推断是否启用移除空框行 */
function inferRemoveEmptyRows(flow, filterRulesCode, explicit) {
  if (explicit === true || explicit === false) return explicit;
  if (flowHasRemoveEmptyRows(flow)) return true;
  if (/remove_empty_ext_rows\s*\(/.test(String(filterRulesCode || ''))) return true;
  return true;
}

function walkNodes(node, visit) {
  if (!node?.type) return;
  visit(node);
  if (!CONTAINER_TYPES.has(node.type)) return;
  for (const branch of CONTAINER_BRANCHES[node.type]) {
    for (const child of node[branch] || []) walkNodes(child, visit);
  }
}

/** 是否包含「移除空框行」节点（通常在 control.loop.body 内，不在 flow 顶层） */
function flowHasRemoveEmptyRows(flow) {
  const f = prepareFlow(flow);
  let found = false;
  for (const root of f.nodes || []) {
    walkNodes(root, (n) => {
      if (n.type === 'builtin.remove_empty_ext_rows') found = true;
    });
  }
  return found;
}

const FlowTree = {
  prepareFlow,
  prepareNode,
  isRulesLoop,
  findRulesLoopNode,
  flowHasRemoveEmptyRows,
  syncRulesLoopRemoveEmpty,
  inferRemoveEmptyRows,
};

export default FlowTree;
