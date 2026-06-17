import { useEffect, useMemo, useRef, useState } from 'react';
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
  const iframeRef = useRef(null);

  useEffect(() => {
    setIframeReady(false);
  }, [iframeSrc]);

  useEffect(() => {
    if (preparing) return undefined;

    const iframe = iframeRef.current;
    if (!iframe) return undefined;

    if (toolId !== 'viz') {
      return undefined;
    }

    let cancelled = false;
    let timer;
    let attempts = 0;

    const markReady = () => {
      if (!cancelled) setIframeReady(true);
    };

    const pollContent = () => {
      if (cancelled) return;
      attempts += 1;
      try {
        const doc = iframe.contentDocument || iframe.contentWindow?.document;
        const root = doc?.getElementById('root');
        if (root?.childElementCount > 0) {
          markReady();
          return;
        }
      } catch {
        markReady();
        return;
      }
      if (attempts >= 120) {
        markReady();
        return;
      }
      timer = setTimeout(pollContent, 500);
    };

    const onLoad = () => {
      clearTimeout(timer);
      timer = setTimeout(pollContent, 150);
    };

    iframe.addEventListener('load', onLoad);
    if (iframe.contentDocument?.readyState === 'complete') {
      onLoad();
    }

    return () => {
      cancelled = true;
      clearTimeout(timer);
      iframe.removeEventListener('load', onLoad);
    };
  }, [iframeSrc, preparing, toolId]);

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
          ref={iframeRef}
          className={iframeClassName}
          src={iframeSrc}
          title={iframeTitle}
          allow="clipboard-read; clipboard-write"
          onLoad={toolId === 'viz' ? undefined : () => setIframeReady(true)}
        />
      </div>
    </div>
  );
}
