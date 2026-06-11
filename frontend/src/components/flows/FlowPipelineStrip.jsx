import { useNavigate } from 'react-router-dom';
import WorkflowPipelineViz from '../forge/WorkflowPipelineViz';

/** 任务列表内嵌流程条（只读，无需额外请求） */
export default function FlowPipelineStrip({ nodes = [], flowId = '', compact = true }) {
  const navigate = useNavigate();
  const steps = (nodes || [])
    .filter((n) => n.tool && n.tool !== 'log' && n.tool !== 'branch')
    .map((n) => ({
      id: n.id,
      kind: n.tool === 'pause' ? 'gate-human' : n.tool,
    }));

  if (!steps.length) {
    return <span className="flows-muted">暂无步骤</span>;
  }

  const onSelect = flowId
    ? (step) => navigate(`/flows/tasks/${encodeURIComponent(flowId)}?node=${encodeURIComponent(step.id)}`)
    : undefined;

  return (
    <div className="flows-pipeline-strip">
      <WorkflowPipelineViz steps={steps} compact={compact} onSelectStep={onSelect} />
    </div>
  );
}
