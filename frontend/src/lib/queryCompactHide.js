/** 查询页简洁视图：可隐藏区块配置 */

export const QUERY_COMPACT_HIDE_DEFS = [
  { key: 'sql', label: 'SQL 编辑器' },
  { key: 'python', label: 'Python 工作区' },
  { key: 'flow', label: '流程编排' },
  { key: 'env', label: '策略参数' },
  { key: 'history', label: '历史快捷' },
];

export function defaultCompactHideMap() {
  return Object.fromEntries(QUERY_COMPACT_HIDE_DEFS.map(({ key }) => [key, false]));
}

export function resolveCompactHideMap(value) {
  return { ...defaultCompactHideMap(), ...(value || {}) };
}

export function serializeCompactHideForSave(map) {
  const out = {};
  for (const { key } of QUERY_COMPACT_HIDE_DEFS) {
    if (map?.[key]) out[key] = true;
  }
  return out;
}

export function mergeCompactHideMap(base, patch) {
  return { ...defaultCompactHideMap(), ...(base || {}), ...(patch || {}) };
}

export function shouldHideInCompact(map, key) {
  return !!resolveCompactHideMap(map)[key];
}

export function showCompactFilterRules(map) {
  return !shouldHideInCompact(map, 'flow');
}
