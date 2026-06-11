import StatusPill from '../ui/StatusPill';

export default function StepTimeline({
  steps = [],
  highlightWaiting = true,
  selectedId = null,
  onSelectStep,
}) {
  if (!steps?.length) {
    return <p className="flows-muted">暂无步骤</p>;
  }

  return (
    <ol className="flows-step-timeline">
      {steps.map((s) => {
        const status = s.status || 'pending';
        const isWaiting = status === 'waiting_human';
        const selected = selectedId === s.step_id;
        return (
          <li
            key={s.step_id}
            className={`flows-step-item flows-step-item--${status}${highlightWaiting && isWaiting ? ' is-active-gate' : ''}${selected ? ' is-selected' : ''}${onSelectStep ? ' is-clickable' : ''}`}
            onClick={onSelectStep ? () => onSelectStep(s) : undefined}
            onKeyDown={onSelectStep ? (e) => { if (e.key === 'Enter') onSelectStep(s); } : undefined}
            role={onSelectStep ? 'button' : undefined}
            tabIndex={onSelectStep ? 0 : undefined}
          >
            <div className="flows-step-head">
              <strong>{s.step_id}</strong>
              {s.tool && <span className="flows-step-tool">{s.tool}</span>}
              <StatusPill status={status} size="sm" />
            </div>
            {s.error && <div className="flows-step-error">{s.error}</div>}
          </li>
        );
      })}
    </ol>
  );
}
