import WorkflowParamsForm from '../forge/WorkflowParamsForm';
import { stepMeta } from '../../lib/workflowCatalog';

/**
 * 单步配置面板：复用 WorkflowParamsForm 控件（策略 / 时间窗 / 模型等）。
 */
export default function ComposeStepPanel({
  stepId,
  kind,
  label,
  stepIndex,
  paramsSchema,
  value,
  onChange,
  models = [],
  hint = null,
}) {
  const meta = stepMeta(kind);

  return (
    <section className="compose-step-panel platform-surface-card" aria-labelledby={`compose-step-${stepId}`}>
      <header className="compose-step-header">
        <span className="compose-step-badge" style={{ '--wf-node-color': meta.color }}>
          {stepIndex + 1}
        </span>
        <div>
          <h3 id={`compose-step-${stepId}`} className="compose-step-title">
            {label || meta.label}
          </h3>
          {meta.desc && <p className="compose-step-desc muted">{meta.desc}</p>}
        </div>
      </header>
      {hint && <p className="compose-step-hint">{hint}</p>}
      <WorkflowParamsForm
        schema={paramsSchema}
        value={value}
        onChange={onChange}
        models={models}
      />
    </section>
  );
}
