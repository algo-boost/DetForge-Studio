import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  api,
  sampleGalleryViewerPath,
  VIZ_OPEN_BODY_KEY,
} from '../api/client';
import { getToolIntegrationSpec } from '../config/toolIntegration';
import { useToolIntegration } from '../hooks/useToolIntegration';
import { formatSampleGalleryError } from '../lib/sampleGallery';
import { buildQueryResultsPath } from '../lib/queryResultsNav';
import { appendViewerNavParams } from '../lib/viewerNav';
import { resolveVizIframeSrcWhilePreparing } from '../lib/vizIframe';
import ToolEmbed from './ToolEmbed';
import ToolMountUnavailable from './ToolMountUnavailable';
import '../styles/viewer.css';

export default function VizToolHost() {
  const spec = getToolIntegrationSpec('viz');
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const session = params.get('session');
  const srcParam = params.get('src');
  const preparing = params.get('preparing') === '1';
  const taskId = params.get('task');
  const returnTo = params.get('returnTo')
    || params.get('return')
    || (taskId ? buildQueryResultsPath(taskId) : '/');
  const [prepareBusy, setPrepareBusy] = useState(preparing && !session && !srcParam);
  const [prepareError, setPrepareError] = useState(null);

  useEffect(() => {
    if (!preparing || session || srcParam) {
      setPrepareBusy(false);
      return undefined;
    }
    let body;
    try {
      const raw = sessionStorage.getItem(VIZ_OPEN_BODY_KEY);
      if (!raw) {
        setPrepareBusy(false);
        return undefined;
      }
      body = JSON.parse(raw);
      sessionStorage.removeItem(VIZ_OPEN_BODY_KEY);
    } catch {
      setPrepareBusy(false);
      return undefined;
    }

    let cancelled = false;
    setPrepareBusy(true);
    setPrepareError(null);
    (async () => {
      try {
        const record = await api.vizOpen(body);
        if (cancelled) return;
        if (!record?.success && record?.error) {
          throw new Error(record.error);
        }
        const path = appendViewerNavParams(sampleGalleryViewerPath(record), {
          taskId: taskId || body.task_id,
          returnTo,
        });
        navigate(path, { replace: true });
      } catch (err) {
        if (cancelled) return;
        setPrepareError(formatSampleGalleryError(err, '样本图库'));
        setPrepareBusy(false);
      }
    })();

    return () => { cancelled = true; };
  }, [preparing, session, srcParam, navigate, taskId, returnTo]);

  const {
    loading,
    integration,
    remoteUrl,
    mountPrefix,
    available,
    mounted,
  } = useToolIntegration('viz');

  const iframeBase = integration === 'remote' && remoteUrl
    ? remoteUrl
    : (mountPrefix || spec.defaultMount);

  const buildSrc = useCallback(({ base, search }) => resolveVizIframeSrcWhilePreparing({
    base: base || iframeBase,
    srcParam,
    session,
    preparing,
    search,
  }), [iframeBase, srcParam, session, preparing]);

  const previewSrc = useMemo(
    () => buildSrc({ base: iframeBase, search: '' }),
    [buildSrc, iframeBase],
  );

  const canOpenExternal = Boolean(session || srcParam);

  if (loading) {
    return (
      <div className="viewer-page viewer-page-immersive">
        <div className="viewer-frame-wrap">
          <div className="viewer-loading-overlay" aria-live="polite">
            <div className="viewer-loading-spinner" aria-hidden />
            <p>{spec.loadingLabel}</p>
          </div>
        </div>
      </div>
    );
  }

  if (integration === 'embedded' && (!available || !mounted)) {
    return (
      <div className="viewer-page viewer-page-immersive">
        <ToolMountUnavailable
          title="样本图库"
          available={available}
          mountPrefix={mountPrefix || spec.defaultMount}
          configLink="/config?section=viz"
          className="platform-surface-card predict-quick-unavailable"
        unavailableHintMounted="COCO 可视化尚未挂载到 /viz，请重启 Flask 服务。"
          unavailableHintMissing="未找到 COCOVisualizer，请在设置中配置 coco_visualizer_root。"
        />
      </div>
    );
  }

  if (prepareError) {
    return (
      <div className="viewer-page viewer-page-immersive">
        <ToolMountUnavailable
          title="样本图库"
          available={false}
          mountPrefix={mountPrefix || spec.defaultMount}
          configLink="/config?section=viz"
          className="platform-surface-card predict-quick-unavailable"
          unavailableHintMounted={prepareError}
          unavailableHintMissing={prepareError}
        />
      </div>
    );
  }

  return (
    <ToolEmbed
      toolId="viz"
      remoteBase={integration === 'remote' ? remoteUrl : undefined}
      mountPrefix={mountPrefix || spec.defaultMount}
      routing="path"
      title={spec.title}
      loadingLabel={spec.loadingLabel}
      preparing={preparing || prepareBusy}
      preparingLabel="正在准备数据集…"
      returnTo={returnTo}
      returnLabel={taskId ? '返回查询结果' : null}
      buildSrc={buildSrc}
      backBarExtra={canOpenExternal ? (
        <a
          className="embed-back-bar-link"
          href={previewSrc}
          target="_blank"
          rel="noopener noreferrer"
        >
          新窗口打开
        </a>
      ) : null}
    />
  );
}
