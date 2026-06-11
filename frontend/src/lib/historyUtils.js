export const HISTORY_TIME_PRESETS = [
  { id: 'all', label: '全部时段' },
  { id: 'today', label: '今天' },
  { id: 'yesterday', label: '昨天' },
  { id: '7days', label: '近7天' },
  { id: '30days', label: '近30天' },
];

export const DEFAULT_HISTORY_FILTERS = {
  q: '',
  timePreset: 'all',
  strategy: '',
  restorableOnly: false,
};

const STRATEGY_COLORS = ['#1d4ed8', '#047857', '#c2410c', '#7c3aed', '#b45309', '#be185d', '#0d9488', '#4f46e5'];

export function strategyColor(name, index = 0) {
  const s = String(name || '');
  let hash = index;
  for (let i = 0; i < s.length; i += 1) hash = (hash + s.charCodeAt(i) * (i + 1)) % STRATEGY_COLORS.length;
  return STRATEGY_COLORS[hash];
}

export function uniqueStrategies(items) {
  const set = new Set();
  (items || []).forEach((item) => {
    const name = String(item.strategy || '').trim();
    if (name) set.add(name);
  });
  return sortStrategies([...set]);
}

export function sortStrategies(names) {
  return [...names].sort((a, b) => a.localeCompare(b, 'zh-CN'));
}

function parseTs(ts) {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

/** 按执行时间（item.ts）计算时段范围 */
export function executionTimeRange(preset) {
  if (!preset || preset === 'all') return { from: null, to: null };
  const now = new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0, 0, 0);
  const endOfNow = () => new Date(now.getFullYear(), now.getMonth(), now.getDate(), now.getHours(), now.getMinutes(), 59, 999);

  if (preset === 'today') {
    return { from: startOfDay(now), to: endOfNow() };
  }
  if (preset === 'yesterday') {
    const y = new Date(now);
    y.setDate(y.getDate() - 1);
    return {
      from: startOfDay(y),
      to: new Date(y.getFullYear(), y.getMonth(), y.getDate(), 23, 59, 59, 999),
    };
  }
  if (preset === '7days') {
    const start = new Date(now.getTime() - 6 * 86400000);
    return { from: startOfDay(start), to: endOfNow() };
  }
  if (preset === '30days') {
    const start = new Date(now.getTime() - 29 * 86400000);
    return { from: startOfDay(start), to: endOfNow() };
  }
  return { from: null, to: null };
}

function inExecutionTimeRange(ts, preset) {
  const d = parseTs(ts);
  if (!d) return true;
  const { from, to } = executionTimeRange(preset);
  if (from && d < from) return false;
  if (to && d > to) return false;
  return true;
}

export function applyHistoryFilters(items, filters = {}) {
  const q = String(filters.q || '').trim().toLowerCase();
  const strategy = filters.strategy || '';
  const timePreset = filters.timePreset || 'all';

  return (items || []).filter((item) => {
    if (!inExecutionTimeRange(item.ts, timePreset)) return false;
    if (strategy && item.strategy !== strategy) return false;
    if (filters.restorableOnly && !(item.snapshot || item.strategy_id)) return false;
    if (q) {
      const hay = [
        item.strategy,
        item.mode_label,
        item.summary,
        item.start,
        item.end,
        item.task_id,
      ].filter(Boolean).join(' ').toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });
}

export function countByStrategy(items, filters = {}) {
  const timePreset = filters.timePreset || 'all';
  const base = (items || []).filter((item) => inExecutionTimeRange(item.ts, timePreset));
  const counts = { '': base.length };
  base.forEach((item) => {
    const key = String(item.strategy || '未知策略').trim() || '未知策略';
    counts[key] = (counts[key] || 0) + 1;
  });
  return counts;
}

export function groupHistoryByStrategy(items) {
  const byStrategy = new Map();
  (items || []).forEach((item) => {
    const key = String(item.strategy || '未知策略').trim() || '未知策略';
    if (!byStrategy.has(key)) byStrategy.set(key, []);
    byStrategy.get(key).push(item);
  });
  return sortStrategies([...byStrategy.keys()]).map((name, index) => ({
    id: name,
    name,
    color: strategyColor(name, index),
    items: byStrategy.get(name),
    count: byStrategy.get(name).length,
  }));
}

export function hasActiveFilters(filters = {}) {
  return Boolean(
    String(filters.q || '').trim()
    || (filters.timePreset && filters.timePreset !== 'all')
    || filters.strategy
    || filters.restorableOnly,
  );
}
