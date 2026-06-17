import SceneHubNav from '../SceneHubNav';

/**
 * 流水线场景统一页壳：Hub 子导航 + 一致滚动/宽度。
 * @param {'default' | 'wide' | 'compose'} layout
 */
export default function FlowsSceneShell({ layout = 'default', className = '', children }) {
  const layoutClass = layout === 'wide'
    ? 'flows-scene--wide'
    : layout === 'compose'
      ? 'flows-scene--compose'
      : '';
  const rootClass = ['panel', 'active', 'flows-scene', layoutClass, className]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={rootClass}>
      <SceneHubNav variant="flows" />
      {children}
    </div>
  );
}
