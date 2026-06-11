import { Link } from 'react-router-dom';

/**
 * embedded 模式下工具未挂载 / 未配置时的占位。
 */
export default function ToolMountUnavailable({
  title = '工具不可用',
  available = false,
  mountPrefix = '',
  unavailableHint,
  unavailableHintMounted,
  unavailableHintMissing,
  configLink,
  configLinkLabel = '打开设置',
  className = 'platform-surface-card predict-quick-unavailable',
}) {
  const message = unavailableHint || (
    available
      ? (unavailableHintMounted || `${title}尚未挂载到 ${mountPrefix || '服务'}，请重启 Flask 服务。`)
      : (unavailableHintMissing || `未找到 ${title}，请在设置中配置对应目录。`)
  );

  return (
    <div className={className}>
      <h4>{title}不可用</h4>
      <p className="muted">{message}</p>
      {configLink ? (
        <Link className="btn btn-sm btn-primary" to={configLink}>{configLinkLabel}</Link>
      ) : null}
    </div>
  );
}
