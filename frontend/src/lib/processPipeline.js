/**
 * process_pipeline 前端辅助（与 studio/flow/process_pipeline.py 对齐）
 * pipeline 为步骤数组，每步含 template_id / id / params。
 */

const ALIAS_TEMPLATE_IDS = {
  random_sample: 'preset_random_sample',
};

const DEFAULT_PIPELINE_BY_PRESETS = {
  'filter,observe,sampling': [
    { template_id: 'preset_observe', params: { stats_label: 'SQL输出类别统计', df_label: 'SQL输出DataFrame', show_stats: 'yes', show_df: 'yes' } },
    { template_id: 'preset_apply_filter_rules', params: {} },
    { template_id: 'preset_observe', params: { stats_label: '过滤之后的类别统计', df_label: '过滤之后的DataFrame', show_stats: 'yes', show_df: 'yes' } },
    { template_id: 'preset_random_sample', params: {} },
    { template_id: 'preset_observe', params: { stats_label: '最终输出的类别统计', df_label: '最终输出的DataFrame', show_stats: 'yes', show_df: 'yes' } },
  ],
  'filter,observe': [
    { template_id: 'preset_observe', params: { stats_label: 'SQL输出类别统计', df_label: 'SQL输出DataFrame', show_stats: 'yes', show_df: 'yes' } },
    { template_id: 'preset_apply_filter_rules', params: {} },
    { template_id: 'preset_observe', params: { stats_label: '过滤后类别统计', df_label: '过滤后DataFrame', show_stats: 'yes', show_df: 'yes' } },
  ],
  'filter,sampling': [
    { template_id: 'preset_apply_filter_rules', params: {} },
    { template_id: 'preset_random_sample', params: {} },
  ],
  observe: [
    { template_id: 'preset_observe', params: { stats_label: '类别统计', df_label: 'DataFrame', show_stats: 'yes', show_df: 'yes' } },
  ],
  filter: [
    { template_id: 'preset_apply_filter_rules', params: {} },
  ],
  sampling: [
    { template_id: 'preset_random_sample', params: {} },
  ],
};

let _seq = 0;

export function newPipelineStepId(prefix = 'ps') {
  _seq += 1;
  return `${prefix}${Date.now().toString(36)}${_seq}`;
}

export function normalizePipelineStep(step, _templatesMap) {
  const raw = step && typeof step === 'object' ? { ...step } : {};
  let tplId = String(raw.template_id || raw.kind || raw.type || '').trim();
  tplId = ALIAS_TEMPLATE_IDS[tplId] || tplId;
  const params = raw.params && typeof raw.params === 'object' && !Array.isArray(raw.params)
    ? { ...raw.params }
    : {};
  return {
    id: raw.id || newPipelineStepId(),
    template_id: tplId,
    params,
  };
}

export function normalizeProcessPipeline(pipeline, templatesMap) {
  let list = pipeline;
  if (list && typeof list === 'object' && !Array.isArray(list) && Array.isArray(list.steps)) {
    list = list.steps;
  }
  if (!Array.isArray(list)) return [];
  return list
    .filter((s) => s && typeof s === 'object')
    .map((s) => normalizePipelineStep(s, templatesMap));
}

export function defaultPipelineFromPresets(pythonPresets = []) {
  const ids = [...new Set((pythonPresets || []).filter(Boolean))].sort();
  const key = ids.join(',');
  let spec = DEFAULT_PIPELINE_BY_PRESETS[key];
  if (!spec) {
    spec = [];
    const order = ['observe', 'filter', 'sampling'];
    for (const pid of order) {
      if (!ids.includes(pid)) continue;
      if (pid === 'observe') {
        spec.push({
          template_id: 'preset_observe',
          params: { stats_label: '类别统计', df_label: 'DataFrame', show_stats: 'yes', show_df: 'yes' },
        });
      } else if (pid === 'filter') {
        spec.push({ template_id: 'preset_apply_filter_rules', params: {} });
      } else if (pid === 'sampling') {
        spec.push({ template_id: 'preset_random_sample', params: {} });
      }
    }
  }
  return spec.map((item) => normalizePipelineStep({
    template_id: item.template_id,
    params: { ...(item.params || {}) },
  }));
}

/**
 * @param {object} draft 策略 draft
 * @param {Record<string, object>} [templatesMap]
 * @returns {Array<{ id: string, template_id: string, params: object }>}
 */
export function ensureProcessPipeline(draft, templatesMap) {
  const strategy = draft && typeof draft === 'object' ? draft : {};
  const existing = strategy.process_pipeline;
  if (Array.isArray(existing) && existing.length) {
    return normalizeProcessPipeline(existing, templatesMap);
  }
  if (existing && typeof existing === 'object' && Array.isArray(existing.steps) && existing.steps.length) {
    return normalizeProcessPipeline(existing.steps, templatesMap);
  }
  const presets = strategy.python_presets;
  if (Array.isArray(presets) && presets.length) {
    return defaultPipelineFromPresets(presets);
  }
  return [];
}

export function moveStep(pipeline, index, delta) {
  const list = [...(pipeline || [])];
  const toIndex = index + delta;
  if (index < 0 || index >= list.length || toIndex < 0 || toIndex >= list.length) {
    return list;
  }
  const [item] = list.splice(index, 1);
  list.splice(toIndex, 0, item);
  return list;
}

export function presetGroupsFromPipeline(pipeline, templatesMap = {}) {
  const seen = [];
  for (const step of normalizeProcessPipeline(pipeline, templatesMap)) {
    const tpl = templatesMap[step.template_id] || {};
    const gid = tpl.preset_group;
    if (gid && !seen.includes(gid)) seen.push(String(gid));
  }
  return seen;
}
