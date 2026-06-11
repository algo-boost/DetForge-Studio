/** 工作流步骤元数据与 params_schema 辅助 */

export const TIME_WINDOW_PRESETS = [
  { value: 'today', label: '今天' },
  { value: 'yesterday', label: '昨天' },
  { value: '7days', label: '近 7 天' },
  { value: '30days', label: '近 30 天' },
];

const STEP_META = {
  query: { label: '数据查询', icon: 'Q', color: '#2563eb', desc: '按策略查询平台数据', group: 'data' },
  predict: { label: '批量预测', icon: 'P', color: '#7c3aed', desc: '对查询任务发起预测', group: 'predict' },
  curation_create: { label: '创建批次', icon: 'C', color: '#059669', desc: '创建筛选归档批次', group: 'curation' },
  'curation-create': { label: '创建批次', icon: 'C', color: '#059669', desc: '创建筛选归档批次', group: 'curation' },
  curation_export: { label: '导出出站', icon: 'E', color: '#0d9488', desc: '导出 COCO 出站包', group: 'curation' },
  'curation-export': { label: '导出出站', icon: 'E', color: '#0d9488', desc: '导出 COCO 出站包', group: 'curation' },
  gate_human: { label: '人工卡点', icon: 'H', color: '#d97706', desc: '等待人工上传或确认', group: 'human' },
  'gate-human': { label: '人工卡点', icon: 'H', color: '#d97706', desc: '等待人工上传或确认', group: 'human' },
  curation_import: { label: '导入 COCO', icon: 'I', color: '#0891b2', desc: '导入编辑后的 COCO', group: 'curation' },
  'curation-import': { label: '导入 COCO', icon: 'I', color: '#0891b2', desc: '导入编辑后的 COCO', group: 'curation' },
  curation_archive: { label: '筛选归档', icon: 'A', color: '#4f46e5', desc: '归档筛选结果', group: 'curation' },
  'curation-archive': { label: '筛选归档', icon: 'A', color: '#4f46e5', desc: '归档筛选结果', group: 'curation' },
  notify: { label: '流程通知', icon: 'N', color: '#64748b', desc: '发送完成/卡点通知', group: 'system' },
  'demo-query': { label: '演示查询', icon: 'D', color: '#2563eb', desc: '演示用模拟查询', group: 'data' },
  'demo-pack': { label: '演示打包', icon: 'D', color: '#059669', desc: '演示用模拟打包', group: 'curation' },
  'demo-notify': { label: '演示通知', icon: 'D', color: '#64748b', desc: '演示用通知', group: 'system' },
  'smoke-query': { label: '冒烟查询', icon: 'S', color: '#2563eb', desc: '样本数据查询（无需业务库）', group: 'data' },
  pause: { label: '人工卡点', icon: 'H', color: '#d97706', desc: '流程暂停，等待人工处理', group: 'human' },
  'gate-human': { label: '人工卡点', icon: 'H', color: '#d97706', desc: '等待人工上传 COCO 或确认', group: 'human' },
  branch: { label: '条件分支', icon: '?', color: '#9333ea', desc: '按条件进入不同分支', group: 'system' },
  log: { label: '日志', icon: 'L', color: '#94a3b8', desc: '记录运行日志', group: 'system' },
};

export function stepMeta(kind) {
  const k = String(kind || 'step');
  return STEP_META[k] || STEP_META[k.replace(/-/g, '_')] || {
    label: k,
    icon: '•',
    color: '#64748b',
    desc: '',
    group: 'system',
  };
}

export function defaultParamsFromSchema(schema) {
  const out = {};
  for (const [key, spec] of Object.entries(schema || {})) {
    if (spec?.default != null) {
      out[key] = spec.default;
    } else if (spec?.type === 'time_window') {
      out[key] = { preset: 'yesterday' };
    } else if (spec?.type === 'strategy') {
      out[key] = '';
    }
  }
  return out;
}

export function schemaForPreset(presetId) {
  if (presetId === 'daily_ng_curation') {
    return {
      strategy_id: { type: 'strategy', default: 'daily_trawl', label: '捞图策略' },
      time_window: { type: 'time_window', default: { preset: 'yesterday' }, label: '时间窗' },
      reviewer: { type: 'string', label: '复核人' },
    };
  }
  if (presetId === 'weekly_predict_eval') {
    return {
      strategy_id: { type: 'strategy', default: 'daily_trawl', label: '策略' },
      model_id: { type: 'model', label: '模型' },
      time_window: { type: 'time_window', default: { preset: '7days' }, label: '时间窗' },
    };
  }
  if (presetId === 'branch_empty_notify') {
    return { notify_on_empty: { type: 'boolean', default: true, label: '空结果也通知' } };
  }
  return {};
}
