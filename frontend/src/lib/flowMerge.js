const SIMPLE_TOP_LEVEL = new Set(['control.loop']);

export function hasComplexFlow(flow) {
  return (flow?.nodes || []).some((n) => !SIMPLE_TOP_LEVEL.has(n.type));
}

export function mergeFlowForSave(originalFlow, rulesFlow) {
  if (!originalFlow?.nodes?.length || !hasComplexFlow(originalFlow)) {
    return rulesFlow || { version: 2, nodes: [] };
  }
  const merged = JSON.parse(JSON.stringify(originalFlow));
  const srcLoop = (rulesFlow?.nodes || []).find(
    (n) => n.type === 'control.loop' && (n.params?.loop_mode || 'rules') === 'rules',
  );
  const dstLoop = merged.nodes.find(
    (n) => n.type === 'control.loop' && (n.params?.loop_mode || 'rules') === 'rules',
  );
  if (dstLoop && srcLoop?.params?.rules?.length) {
    dstLoop.params.rules = JSON.parse(JSON.stringify(srcLoop.params.rules));
  }
  if (dstLoop?.body && srcLoop?.body) {
    const wantRemove = srcLoop.body.some((n) => n.type === 'builtin.remove_empty_ext_rows');
    const hasRemove = dstLoop.body.some((n) => n.type === 'builtin.remove_empty_ext_rows');
    if (wantRemove && !hasRemove) {
      dstLoop.body.push({ id: `rm_${Date.now()}`, type: 'builtin.remove_empty_ext_rows', params: {} });
    } else if (!wantRemove && hasRemove) {
      dstLoop.body = dstLoop.body.filter((n) => n.type !== 'builtin.remove_empty_ext_rows');
    }
  }
  return merged;
}

export function uiFilterMode(backendMode) {
  if (backendMode === 'code') return 'code';
  if (backendMode === 'split') return 'split';
  return 'rules';
}

export function backendFilterMode(uiMode) {
  return uiMode === 'code' ? 'code' : uiMode === 'split' ? 'split' : 'flow';
}

/** process_data 调用了 apply_filter_rules 但未内联 def */
export function pythonNeedsFilterRules(code) {
  const text = String(code || '');
  if (/def\s+apply_filter_rules\s*\(/.test(text)) return false;
  return /\bapply_filter_rules\s*\(/.test(text);
}
