/** 样本图库 /viewer 导航参数 */

export function appendViewerNavParams(path, { taskId, returnTo } = {}) {
  const raw = String(path || '/viewer');
  const qIdx = raw.indexOf('?');
  const pathname = qIdx >= 0 ? raw.slice(0, qIdx) : raw;
  const params = new URLSearchParams(qIdx >= 0 ? raw.slice(qIdx + 1) : '');
  if (taskId != null && String(taskId).trim() !== '') {
    params.set('task', String(taskId));
  }
  if (returnTo != null && String(returnTo).trim() !== '') {
    params.set('returnTo', String(returnTo));
  }
  const q = params.toString();
  return q ? `${pathname}?${q}` : pathname;
}

export function buildQueryResultsReturnPath(taskId) {
  if (taskId != null && String(taskId).trim() !== '') {
    return `/query-results?task=${encodeURIComponent(String(taskId))}`;
  }
  return '/query-results';
}
