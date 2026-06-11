/** 查询页 UI 模式（简洁 / 完整） */

export const QUERY_UI_MODE_COMPACT = 'compact';
export const QUERY_UI_MODE_FULL = 'full';

export const QUERY_UI_MODE_OPTIONS = [
  { id: QUERY_UI_MODE_COMPACT, label: '简洁' },
  { id: QUERY_UI_MODE_FULL, label: '完整' },
];

const STORAGE_KEY = 'iisp.query_ui_mode';

export function loadQueryUiModePreference() {
  try {
    return localStorage.getItem(STORAGE_KEY) || QUERY_UI_MODE_FULL;
  } catch {
    return QUERY_UI_MODE_FULL;
  }
}

export function saveQueryUiModePreference(mode) {
  try {
    localStorage.setItem(STORAGE_KEY, mode || QUERY_UI_MODE_FULL);
  } catch { /* ignore */ }
}

export function resolveQueryUiMode(mode, fallback = QUERY_UI_MODE_FULL) {
  const m = mode || loadQueryUiModePreference();
  return m === QUERY_UI_MODE_COMPACT ? QUERY_UI_MODE_COMPACT : (fallback || QUERY_UI_MODE_FULL);
}

export function queryUiModeLabel(mode) {
  return QUERY_UI_MODE_OPTIONS.find((o) => o.id === mode)?.label || mode || '完整';
}
