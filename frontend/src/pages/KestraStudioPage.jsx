import { useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api } from '../api/client';
import EmbedBackBar from '../components/EmbedBackBar';
import SceneHubNav from '../components/SceneHubNav';
import '../styles/viewer.css';

export default function KestraStudioPage() {
  const [searchParams] = useSearchParams();
  const path = searchParams.get('path') || '';
  const [config, setConfig] = useState(null);
  const [error, setError] = useState('');
  const [iframeReady, setIframeReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const q = path ? `?path=${encodeURIComponent(path)}` : '';
        const r = await api.flowKestraStudio(q);
        if (cancelled) return;
        if (r.success) {
          setConfig(r.data || null);
          setError('');
        } else {
          setError(r.error || '加载 Kestra 配置失败');
        }
      } catch (e) {
        if (!cancelled) setError(String(e.message || e));
      }
    })();
    return () => { cancelled = true; };
  }, [path]);

  const iframeSrc = config?.embed_url || '';
  const openUrl = config?.external_url || config?.ui_root || iframeSrc || '';

  useEffect(() => {
    setIframeReady(false);
  }, [iframeSrc]);

  const hint = useMemo(() => {
    if (!config?.enabled) {
      return 'Kestra 未启用。请运行 platform-start.sh 启动 Kestra（:8080）后刷新。';
    }
    if (config?.proxy_enabled) {
      return '已通过 IISP 同源代理自动登录 Kestra。生产 Flow 仍以 Git Catalog 为准。';
    }
    return '直连 Kestra 需在 iframe 内登录（admin@kestra.io）。生产 Flow 仍以 Git Catalog 为准。';
  }, [config?.enabled]);

  if (error) {
    return (
      <div className="panel active flows-page">
        <SceneHubNav variant="flows" />
        <div className="empty-state">{error}</div>
        <Link to="/flows" className="btn btn-sm">返回 Flow 目录</Link>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="panel active flows-page">
        <SceneHubNav variant="flows" />
        <div className="empty-state">加载 Kestra 编排器…</div>
      </div>
    );
  }

  if (!config.enabled) {
    return (
      <div className="panel active flows-page flows-page--wide">
        <SceneHubNav variant="flows" />
        <header className="flows-page-header">
          <div>
            <h1 className="flows-page-title">Kestra 编排器</h1>
            <p className="flows-page-desc">{hint}</p>
          </div>
          <Link to="/flows" className="btn btn-sm">Flow 目录</Link>
        </header>
      </div>
    );
  }

  return (
    <div className="viewer-page viewer-page-immersive kestra-studio-page">
      <EmbedBackBar
        returnTo="/flows"
        returnLabel="Flow 目录"
        extra={openUrl ? (
          <a
            href={openUrl}
            className="embed-back-bar-link"
            target="_blank"
            rel="noreferrer"
          >
            新窗口打开
          </a>
        ) : null}
      />
      <SceneHubNav variant="flows" className="kestra-studio-hub" />
      <p className="kestra-studio-hint">{hint}</p>
      <div className="viewer-frame-wrap">
        {(!iframeReady) && (
          <div className="viewer-loading-overlay" aria-live="polite">
            <div className="viewer-loading-spinner" aria-hidden />
            <p>加载 Kestra UI…</p>
          </div>
        )}
        <iframe
          key={iframeSrc}
          className="viewer-iframe"
          src={iframeSrc}
          title="Kestra 编排器"
          allow="clipboard-read; clipboard-write"
          onLoad={() => setIframeReady(true)}
        />
      </div>
    </div>
  );
}
