/** 查询结果页路由与最近 task 记忆 */

const LAST_TASK_KEY = 'iisp.last_query_task_id';

export function buildQueryResultsPath(taskId) {
  if (taskId != null && String(taskId).trim() !== '') {
    return `/query-results?task=${encodeURIComponent(String(taskId))}`;
  }
  return '/query-results';
}

export function saveLastQueryTaskId(taskId) {
  if (taskId == null || String(taskId).trim() === '') return;
  try {
    localStorage.setItem(LAST_TASK_KEY, String(taskId));
  } catch { /* ignore */ }
}

export function loadLastQueryTaskId() {
  try {
    return localStorage.getItem(LAST_TASK_KEY) || '';
  } catch {
    return '';
  }
}
