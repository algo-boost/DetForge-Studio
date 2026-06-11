import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import EmbedBackBar from './EmbedBackBar';
import { getToolIntegrationSpec } from '../config/toolIntegration';
import { buildToolIframeSrc } from '../lib/toolIntegration';
import '../styles/viewer.css';

/**
 * 通用 remote 集成 iframe（Query hash / viz path 等）。
 */
export default function ToolEmbed({
  toolId = 'query',
  page,
  segment: segmentProp,
  remoteBase,
  mountPrefix,
  routing,
  title,
  loadingLabel,
  preparingLabel,
  preparing = false,
  returnTo: returnToProp,
  returnLabel,
  backBarExtra,
  buildSrc,
  wrapClassName,
  iframeClassName = 'viewer-iframe',
}) {
  const spec = getToolIntegrationSpec(toolId);
  const location = useLocation();

  const segment = useMemo(() => {
    if (segmentProp) return segmentProp;
    if (page) return page === 'admin' ? 'strategies' : page;
    const p = location.pathname.replace(/^\//, '') || '';
    return p === 'admin' ? 'strategies' : p;
  }, [segmentProp, page, location.pathname]);

  const base = (remoteBase || mountPrefix || spec.defaultMount).replace(/\/$/, '');
  const routeMode = routing || spec.routing;

  const iframeSrc = useMemo(() => {
    if (buildSrc) return buildSrc({ base, segment, search: location.search, routing: routeMode });
    return buildToolIframeSrc({
      base,
      routing: routeMode,
      segment,
      search: location.search,
      hashRouting: routeMode === 'hash',
    });
  }, [base, segment, location.search, routeMode, buildSrc]);

  const [iframeReady, setIframeReady] = useState(false);

  useEffect(() => {
    setIframeReady(false);
  }, [iframeSrc]);

  const returnTo = returnToProp ?? (location.pathname + location.search);
  const iframeTitle = title || spec.title;
  const overlayText = preparing
    ? (preparingLabel || '正在准备…')
    : (loadingLabel || spec.remoteLoadingLabel || spec.loadingLabel);
  const showOverlay = preparing || !iframeReady;
  const wrapCls = wrapClassName || `viewer-page viewer-page-immersive tool-embed tool-embed-${toolId}`;

  return (
    <div className={wrapCls}>
      <EmbedBackBar returnTo={returnTo} returnLabel={returnLabel ?? '返回'} extra={backBarExtra} />
      <div className="viewer-frame-wrap">
        {showOverlay && (
          <div className="viewer-loading-overlay" aria-live="polite">
            <div className="viewer-loading-spinner" aria-hidden />
            <p>{overlayText}</p>
          </div>
        )}
        <iframe
          key={iframeSrc}
          className={iframeClassName}
          src={iframeSrc}
          title={iframeTitle}
          allow="clipboard-read; clipboard-write"
          onLoad={() => setIframeReady(true)}
        />
      </div>
    </div>
  );
}
