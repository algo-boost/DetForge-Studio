import { statusLabel, statusTone, STATUS_MAP } from './statusMap';

/**
 * 统一状态 Pill（Query / Flow / Job / Workflow）
 * @param {{ status?: string, map?: Record<string, { label: string, tone: string }>, className?: string, size?: 'sm' | 'md' }} props
 */
export default function StatusPill({ status, map, className = '', size = 'md' }) {
  const m = map || STATUS_MAP;
  const label = statusLabel(status, m);
  const tone = statusTone(status, m);
  const sizeClass = size === 'sm' ? ' status-pill--sm' : '';
  return (
    <span className={`status-pill status-pill--${tone}${sizeClass}${className ? ` ${className}` : ''}`}>
      {label}
    </span>
  );
}

export { STATUS_MAP, statusLabel, statusTone } from './statusMap';
export {
  WORKFLOW_RUN_STATUS_MAP,
  WORKFLOW_STEP_STATUS_MAP,
  QUERY_STATUS_MAP,
} from './statusMap';
