import { useState } from 'react';
import FlowParamsForm from './FlowParamsForm';
import FlowGraphDrawer from './FlowGraphDrawer';
import PipelineYamlDrawer from './PipelineYamlDrawer';
import { defaultParamsFromSchema } from '../../lib/workflowCatalog';

export default function FlowCard({
  flow,
  busy = false,
  onRun,
  onSync,
}) {
  const [params, setParams] = useState(() => defaultParamsFromSchema(flow.params_schema));
  const [yamlOpen, setYamlOpen] = useState(false);
  const [graphOpen, setGraphOpen] = useState(false);
  const [running, setRunning] = useState(false);

  const handleRun = async () => {
    if (!onRun) return;
    setRunning(true);
    try {
      await onRun(flow, params);
    } finally {
      setRunning(false);
    }
  };

  const engineLabel = flow.engine === 'workflow' ? '组合编排' : 'Legacy';
  const releaseTag = flow.release_version
    ? `${flow.release_version}${flow.release_status === 'published' ? '' : ' (draft)'}`
    : null;

  return (
    <article className={`flows-card panel${flow.valid === false ? ' flows-card--invalid' : ''}`}>
      <header className="flows-card-head">
        <div>
          <div className="flows-card-id">{flow.id}</div>
          <h3 className="flows-card-title">{flow.label || flow.id}</h3>
        </div>
        <span className={`flows-engine-pill flows-engine-pill--${flow.engine}`}>{engineLabel}</span>
      </header>

      {flow.description && (
        <p className="flows-card-desc">{String(flow.description).trim().split('\n')[0]}</p>
      )}

      <div className="flows-card-meta">
        {releaseTag && <span>Release {releaseTag}</span>}
        {flow.catalog_version && <span>v{flow.catalog_version}</span>}
        {flow.nodes?.length > 0 && (
          <span>
            {flow.nodes.map((n) => n.id).join(' → ')}
          </span>
        )}
      </div>

      {flow.runnable && (
        <div className="flows-card-run">
          <FlowParamsForm
            schema={flow.params_schema || {}}
            value={params}
            onChange={setParams}
          />
          <button
            type="button"
            className="btn btn-sm btn-primary"
            disabled={busy || running}
            onClick={handleRun}
          >
            运行
          </button>
        </div>
      )}


      <footer className="flows-card-actions">
        <button type="button" className="btn btn-sm" onClick={() => setGraphOpen(true)}>
          流程图
        </button>
        <button type="button" className="btn btn-sm" onClick={() => setYamlOpen(true)}>
          查看 YAML
        </button>
      </footer>

      <FlowGraphDrawer
        flowId={flow.id}
        open={graphOpen}
        onClose={() => setGraphOpen(false)}
        mode="design"
      />
      <PipelineYamlDrawer
        flowId={flow.id}
        open={yamlOpen}
        onClose={() => setYamlOpen(false)}
      />
    </article>
  );
}
