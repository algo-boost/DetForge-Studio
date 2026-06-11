export const HISTORY_KEY = 'pc_history';
export const HISTORY_CATEGORIES_KEY = 'pc_history_categories';

const DEFAULT_CATEGORY_COLORS = ['#1d4ed8', '#047857', '#c2410c', '#7c3aed', '#b45309', '#be185d'];

export function loadHistory() {
  try {
    const list = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function persistHistory(list) {
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list.slice(0, 50)));
}

export function saveHistoryEntry(entry) {
  persistHistory([entry, ...loadHistory()]);
}

export function clearHistory() {
  localStorage.removeItem(HISTORY_KEY);
}

export function updateHistoryEntry(ts, patch) {
  if (!ts) return false;
  const list = loadHistory();
  const idx = list.findIndex((e) => e.ts === ts);
  if (idx < 0) return false;
  list[idx] = { ...list[idx], ...patch };
  persistHistory(list);
  return true;
}

export function setHistoryCategory(ts, categoryId) {
  return updateHistoryEntry(ts, { category_id: categoryId || null });
}

export function loadCategories() {
  try {
    const list = JSON.parse(localStorage.getItem(HISTORY_CATEGORIES_KEY) || '[]');
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export function saveCategories(categories) {
  localStorage.setItem(HISTORY_CATEGORIES_KEY, JSON.stringify(categories || []));
}

export function addCategory(name) {
  const trimmed = String(name || '').trim();
  if (!trimmed) return null;
  const cats = loadCategories();
  if (cats.some((c) => c.name === trimmed)) return null;
  const id = `cat_${Date.now().toString(36)}`;
  const color = DEFAULT_CATEGORY_COLORS[cats.length % DEFAULT_CATEGORY_COLORS.length];
  const next = [...cats, { id, name: trimmed, color }];
  saveCategories(next);
  return next.find((c) => c.id === id);
}

export function renameCategory(id, name) {
  const trimmed = String(name || '').trim();
  if (!id || !trimmed) return false;
  const cats = loadCategories();
  const idx = cats.findIndex((c) => c.id === id);
  if (idx < 0) return false;
  cats[idx] = { ...cats[idx], name: trimmed };
  saveCategories(cats);
  return true;
}

export function deleteCategory(id) {
  const cats = loadCategories().filter((c) => c.id !== id);
  saveCategories(cats);
  const list = loadHistory().map((e) => (
    e.category_id === id ? { ...e, category_id: null } : e
  ));
  persistHistory(list);
  return true;
}

export function getCategoryMap(categories = loadCategories()) {
  return Object.fromEntries((categories || []).map((c) => [c.id, c]));
}

export function buildHistoryEntry({
  strategy, strategyId, start, end, startRaw, endRaw, count, sampleSize, randomSeed, snapshot, result, summary, modeLabel, categoryId,
}) {
  const entry = {
    strategy,
    strategy_id: strategyId || '',
    start,
    end,
    start_raw: startRaw,
    end_raw: endRaw,
    count,
    sample_size: sampleSize,
    random_seed: randomSeed,
    time: new Date().toLocaleString('zh-CN'),
    ts: new Date().toISOString(),
    snapshot,
    summary: summary || '',
    mode_label: modeLabel || '',
    category_id: categoryId || null,
  };
  if (result) {
    if (result.input_rows != null) entry.sql_rows = result.input_rows;
    if (result.output_rows != null) entry.filter_rows = result.output_rows;
    if (result.task_id) entry.task_id = result.task_id;
    if (result.execution_time != null) entry.execution_time = result.execution_time;
  }
  return entry;
}
