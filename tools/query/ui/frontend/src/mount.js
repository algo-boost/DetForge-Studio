/** IISP 同进程挂载前缀（templates/index.html 注入 window.__QUERY_TOOL_MOUNT__）。 */
export function getMountPrefix() {
  return typeof window !== 'undefined' ? (window.__QUERY_TOOL_MOUNT__ || '') : '';
}

/** REST 仍走 IISP 根 /api；仅静态资源加挂载前缀。 */
export function mountUrl(url) {
  if (!url || typeof url !== 'string') return url;
  const mount = getMountPrefix();
  if (!mount) return url;
  if (url.startsWith('/api/')) return url;
  if (url.startsWith('/static/')) return `${mount}${url}`;
  return url;
}
