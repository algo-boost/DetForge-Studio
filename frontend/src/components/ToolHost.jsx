import { Suspense } from 'react';
import { getToolIntegrationSpec } from '../config/toolIntegration';
import { useToolIntegration } from '../hooks/useToolIntegration';
import ToolEmbed from './ToolEmbed';
import ToolMountUnavailable from './ToolMountUnavailable';

/**
 * 通用 ToolHost：
 * - embedded + pages → 直渲染 React 子页面（Query）
 * - embedded + 无 pages → 挂载 iframe（viz / unify）
 * - remote / standalone → remote iframe
 */
export default function ToolHost({
  toolId,
  page,
  pages,
  segment,
  embedProps = {},
}) {
  const spec = getToolIntegrationSpec(toolId);
  const {
    loading,
    integration,
    remoteUrl,
    standaloneUrl,
    mountPrefix,
    available,
    mounted,
  } = useToolIntegration(toolId);

  const hasPages = pages && Object.keys(pages).length > 0;
  const Page = hasPages && ((page && pages[page]) || pages[Object.keys(pages)[0]]);

  if (loading) {
    return (
      <div className="panel active" style={{ padding: 24 }}>
        {spec.loadingLabel}
      </div>
    );
  }

  if (integration === 'remote' && remoteUrl) {
    return (
      <ToolEmbed
        toolId={toolId}
        page={page}
        segment={segment}
        remoteBase={remoteUrl}
        mountPrefix={mountPrefix}
        {...embedProps}
      />
    );
  }

  if (!hasPages) {
    if (integration === 'standalone' && standaloneUrl) {
      return (
        <ToolEmbed
          toolId={toolId}
          segment={segment}
          remoteBase={standaloneUrl}
          mountPrefix={mountPrefix}
          {...embedProps}
        />
      );
    }

    if (integration === 'embedded' && (!available || !mounted)) {
      return (
        <ToolMountUnavailable
          title={embedProps.unavailableTitle || spec.title}
          available={available}
          mountPrefix={mountPrefix || spec.defaultMount}
          unavailableHint={embedProps.unavailableHint}
          unavailableHintMounted={embedProps.unavailableHintMounted}
          unavailableHintMissing={embedProps.unavailableHintMissing}
          configLink={embedProps.configLink}
          configLinkLabel={embedProps.configLinkLabel}
          className={embedProps.unavailableClassName}
        />
      );
    }

    if (integration === 'embedded') {
      return (
        <ToolEmbed
          toolId={toolId}
          segment={segment}
          mountPrefix={mountPrefix}
          {...embedProps}
        />
      );
    }

    return (
      <div className="panel active" style={{ padding: 24 }}>
        未配置页面组件
      </div>
    );
  }

  if (!Page) {
    return (
      <div className="panel active" style={{ padding: 24 }}>
        未配置页面组件
      </div>
    );
  }

  return (
    <Suspense fallback={<div className="panel active" style={{ padding: 24 }}>{spec.loadingLabel}</div>}>
      <Page />
    </Suspense>
  );
}
