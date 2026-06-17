/** 简洁模式下可隐藏的查询页区块（由策略 query_compact_hide 配置） */

export const QUERY_COMPACT_HIDE_DEFS = [
  { key: 'data_source', label: '数据源切换' },
  { key: 'predict_job', label: '预测批次选择' },
  { key: 'strategy_params', label: '策略参数区' },
  { key: 'filter_rules', label: '筛选规则区（仅规则表）' },
  { key: 'preview_button', label: '「预览筛选」按钮' },
  { key: 'preview_stats', label: '预览统计信息' },
  { key: 'compact_hint', label: '简洁模式说明条' },
  { key: 'strategy_tools', label: '顶栏保存/导入/导出' },
];

/** 简洁模式默认展示筛选规则，不隐藏 */
const DEFAULT_HIDE = {
  preview_button: true,
  compact_hint: false,
  filter_rules: false,
};

export function defaultCompactHideMap() {
  const map = {};
  for (const { key } of QUERY_COMPACT_HIDE_DEFS) {
    map[key] = DEFAULT_HIDE[key] === true;
  }
  return map;
}

export function resolveCompactHideMap(strategy) {
  return mergeCompactHideMap(strategy?.query_compact_hide);
}

export function shouldHideInCompact(compactHide, key, uiMode) {
  if (uiMode !== 'compact') return false;
  return compactHide?.[key] === true;
}

/** 简洁模式是否展示筛选规则（仅规则 Builder，无代码切换） */
export function showCompactFilterRules(compactHide, uiMode) {
  return uiMode === 'compact' && !shouldHideInCompact(compactHide, 'filter_rules', uiMode);
}

/** 合并为完整隐藏映射（true=隐藏） */
export function mergeCompactHideMap(raw) {
  const map = defaultCompactHideMap();
  if (!raw || typeof raw !== 'object') return map;
  for (const { key } of QUERY_COMPACT_HIDE_DEFS) {
    if (raw[key] === true) map[key] = true;
    if (raw[key] === false) map[key] = false;
  }
  return map;
}

/** 写入策略 JSON：保留全部键及 true/false，便于取消「默认隐藏」项 */
export function serializeCompactHideForSave(raw) {
  const map = mergeCompactHideMap(raw);
  const out = {};
  for (const { key } of QUERY_COMPACT_HIDE_DEFS) {
    out[key] = !!map[key];
  }
  return out;
}

/** @deprecated 仅 true 键；请用 serializeCompactHideForSave */
export function normalizeCompactHidePayload(raw) {
  const full = serializeCompactHideForSave(raw);
  const sparse = {};
  for (const { key } of QUERY_COMPACT_HIDE_DEFS) {
    if (full[key]) sparse[key] = true;
  }
  return Object.keys(sparse).length ? sparse : undefined;
}
