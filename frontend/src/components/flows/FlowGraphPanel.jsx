import { useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import WorkflowPipelineViz from '../forge/WorkflowPipelineViz';
import FlowIntroCard from './FlowIntroCard';
import FlowNodeDetailPanel from './FlowNodeDetailPanel';

/**
 * 只读中文流程图：设计态加载 manifest；运行态合并步骤 I/O。
 * graph: 可选预加载图（运行详情页传入）
 */
export default function FlowGraphPanel({
  flowId,
  graph: graphProp = null,
  mode = 'design',
  compact = false,
  initialSelectedId = null,
}) {
  const [graph, setGraph] = useState(graphProp);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedId, setSelectedId] = useState(initialSelectedId);

  useEffect(() => {
    if (graphProp) {
      setGraph(graphProp);
      setError('');
      return undefined;
    }
    if (!flowId) return undefined;
    let cancelled = false;
    setLoading(true);
    api.flowPipelineGraph(flowId).then((r) => {
      if (cancelled) return;
      if (r.success) {
        setGraph(r.data || null);
        setError('');
      } else {
        setGraph(null);
        setError(r.error || '加载流程图失败');
      }
    }).catch((e) => {
      if (!cancelled) setError(String(e.message || e));
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [flowId, graphProp]);

  const vizSteps = useMemo(() => {
    const nodes = (graph?.nodes || []).filter((n) => n.node_kind !== 'log');
    return nodes.map((n) => ({
      id: n.id,
      kind: n.tool_id || n.kind,
      status: n.status,
      duration: n.duration_seconds,
      _node: n,
    }));
  }, [graph]);

  const selectedNode = useMemo(() => {
    if (!selectedId) return null;
    return (graph?.nodes || []).find((n) => n.id === selectedId) || null;
  }, [graph, selectedId]);

  useEffect(() => {
    if (initialSelectedId) {
      setSelectedId(initialSelectedId);
    }
  }, [initialSelectedId]);

  useEffect(() => {
    if (!selectedId && vizSteps.length) {
      const active = vizSteps.find((s) => s.status === 'running' || s.status === 'waiting_human');
      setSelectedId((active || vizSteps[0])?.id || null);
    }
  }, [vizSteps, selectedId]);

  if (loading) return <p className="flows-muted">加载流程图…</p>;
  if (error) return <p className="flows-step-error">{error}</p>;
  if (!graph?.nodes?.length) return <p className="flows-muted">暂无流程节点</p>;

  const flowReadable = graph?.readable || null;

  return (
    <div className={`flows-graph-panel${compact ? ' flows-graph-panel--compact' : ''}`}>
      <FlowIntroCard readable={flowReadable} className="flows-graph-panel-intro" />
      <div className="flows-graph-panel-body">
        <div className="flows-graph-viz-wrap">
          <WorkflowPipelineViz
            steps={vizSteps}
            compact={compact}
            selectedId={selectedId}
            onSelectStep={(step) => setSelectedId(step.id)}
          />
        </div>
        <FlowNodeDetailPanel
          node={selectedNode}
          mode={mode}
          flowReadable={flowReadable}
        />
      </div>
    </div>
  );
}
