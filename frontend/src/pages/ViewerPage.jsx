import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import '../styles/viewer.css';

function resolveIframeSrc(srcParam, session) {
  if (srcParam) {
    try {
      const decoded = decodeURIComponent(srcParam);
      if (decoded.startsWith('/viz')) return decoded;
    } catch {
      /* ignore */
    }
  }
  if (session) {
    return `/viz/?defectloop_session=${encodeURIComponent(session)}`;
  }
  return '/viz/';
}

export default function ViewerPage() {
  const [params] = useSearchParams();
  const session = params.get('session');
  const srcParam = params.get('src');
  const preparing = params.get('preparing') === '1';
  const iframeSrc = useMemo(
    () => resolveIframeSrc(srcParam, session),
    [srcParam, session],
  );
  const [iframeReady, setIframeReady] = useState(false);

  useEffect(() => {
    setIframeReady(false);
  }, [iframeSrc, preparing]);

  const showOverlay = preparing || !iframeReady;
  const canOpenExternal = iframeSrc && iframeSrc !== '/viz/';

  return (
    <div className="viewer-page viewer-page-immersive">
      <div className="viewer-frame-wrap">
        {showOverlay && (
          <div className="viewer-loading-overlay" aria-live="polite">
            <div className="viewer-loading-spinner" aria-hidden />
            <p>{preparing ? '正在准备数据集…' : '正在加载样本图库…'}</p>
          </div>
        )}
        <iframe
          key={iframeSrc}
          className="viewer-iframe"
          src={preparing && !srcParam && !session ? '/viz/' : iframeSrc}
          title="样本图库"
          allow="clipboard-read; clipboard-write"
          onLoad={() => setIframeReady(true)}
        />
      </div>
      <div className="viewer-hover-bar" aria-label="看图页快捷操作">
        <div className="viewer-hover-bar-inner">
          <Link className="viewer-hover-btn" to="/">返回查询</Link>
          {canOpenExternal && (
            <a
              className="viewer-hover-btn"
              href={iframeSrc}
              target="_blank"
              rel="noopener noreferrer"
            >
              新窗口
            </a>
          )}
        </div>
      </div>
    </div>
  );
}
