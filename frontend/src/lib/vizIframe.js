/**
 * 构建 COCO 可视化 iframe URL（本地 /viz 或 remote base）。
 */
export function resolveVizIframeSrc({ base, srcParam, session, search = '' }) {
  const root = String(base || '/viz').replace(/\/$/, '');
  const qs = search || '';

  if (srcParam) {
    try {
      const decoded = decodeURIComponent(srcParam);
      if (decoded.startsWith('/viz') || decoded.startsWith(root)) {
        return decoded;
      }
    } catch {
      /* ignore */
    }
  }

  if (session) {
    const sep = qs ? (qs.startsWith('?') ? '&' : '?') : '?';
    const extra = qs ? `${sep}${qs.replace(/^\?/, '')}` : '';
    return `${root}/?defectloop_session=${encodeURIComponent(session)}${extra}`;
  }

  if (qs) {
    return `${root}/${qs.startsWith('?') ? qs : `?${qs}`}`.replace(/\/+\?/, '/?');
  }
  return `${root}/`;
}

export function resolveVizIframeSrcWhilePreparing(opts) {
  const { preparing, srcParam, session, base } = opts;
  if (preparing && !srcParam && !session) {
    return `${String(base || '/viz').replace(/\/$/, '')}/`;
  }
  return resolveVizIframeSrc(opts);
}
