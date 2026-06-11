import { stepMeta } from '../../lib/workflowCatalog';
import { formatDuration } from '../../lib/time';
import { statusLabel, WORKFLOW_STEP_STATUS_MAP } from '../ui/statusMap';

/**
 * 横向流程图：步骤节点 + 连线 + 可选运行状态。
 * steps: [{ id, kind, status?, duration? }]
 */
export default function WorkflowPipelineViz({
  steps = [],
  compact = false,
  onSelectStep,
  selectedId = null,
  statusMap = WORKFLOW_STEP_STATUS_MAP,
}) {
  if (!steps.length) {
    return <p className="wf-viz-empty">暂无步骤</p>;
  }

  return (
    <div className={`wf-viz${compact ? ' wf-viz-compact' : ''}`} role="list">
      {steps.map((step, idx) => {
        const meta = stepMeta(step.kind);
        const st = step.status;
        const clickable = Boolean(onSelectStep);
        return (
          <div key={step.id || idx} className="wf-viz-segment" role="listitem">
            {idx > 0 && (
              <div className={`wf-viz-arrow${st === 'skipped' ? ' is-skipped' : ''}`} aria-hidden>
                <svg width="28" height="16" viewBox="0 0 28 16">
                  <path d="M0 8h20M16 4l8 4-8 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
                </svg>
              </div>
            )}
            <button
              type="button"
              className={`wf-viz-node wf-viz-node-${st || 'default'}${clickable ? ' is-clickable' : ''}${selectedId === step.id ? ' is-selected' : ''}`}
              style={{ '--wf-node-color': meta.color }}
              onClick={clickable ? () => onSelectStep(step) : undefined}
              disabled={!clickable}
              title={meta.desc}
            >
              <span className="wf-viz-node-icon" aria-hidden>{meta.icon}</span>
              <span className="wf-viz-node-label">{meta.label}</span>
              {!compact && <span className="wf-viz-node-id">{step.id}</span>}
              {st && (
                <span className={`wf-viz-node-status wf-viz-st-${st}`}>
                  {statusLabel(st, statusMap)}
                </span>
              )}
              {formatDuration(step.duration) && (
                <span className="wf-viz-node-duration">{formatDuration(step.duration)}</span>
              )}
            </button>
          </div>
        );
      })}
    </div>
  );
}