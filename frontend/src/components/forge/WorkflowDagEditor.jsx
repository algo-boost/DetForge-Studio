import { useCallback, useMemo, useRef, useState } from 'react';
import {
  EDGE_WHEN,
  autoLayout,
  compileGraphDefinition,
  defaultNodeParams,
  graphPreset,
  inferParamsSchema,
  listStepKinds,
  newNodeId,
  resetNodeSeq,
  schemaForPreset,
  WF_STEP_DRAG_MIME,
} from '../../lib/workflowGraph';
import { FLOW_NODE_H, FLOW_NODE_W } from '../../lib/workflowFlowGeometry';
import { defaultParamsFromSchema, stepMeta } from '../../lib/workflowCatalog';
import WorkflowFlowCanvas from './WorkflowFlowCanvas';
import WorkflowParamsForm from './WorkflowParamsForm';

const PALETTE_GROUPS = [
  { key: 'data', label: '数据' },
  { key: 'predict', label: '预测' },
  { key: 'curation', label: '筛选归档' },
  { key: 'human', label: '人工' },
  { key: 'system', label: '系统' },
];

export default function WorkflowDagEditor({ models = [], onLaunch, busy = false }) {
  const [preset, setPreset] = useState('daily_ng_curation');
  const [graph, setGraph] = useState(() => graphPreset('daily_ng_curation'));
  const [params, setParams] = useState(() => defaultParamsFromSchema(schemaForPreset('daily_ng_curation')));
  const [name, setName] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [connectMode, setConnectMode] = useState(false);
  const [edgeWhen, setEdgeWhen] = useState('always');
  const [inspectorOpen, setInspectorOpen] = useState(true);
  const [draggingKind, setDraggingKind] = useState(null);
  const paletteDragRef = useRef(false);

  const schema = useMemo(() => inferParamsSchema(graph.nodes), [graph.nodes]);
  const selectedNode = graph.nodes.find((n) => n.id === selectedId);
  const stepKinds = listStepKinds();

  const loadPreset = (id) => {
    resetNodeSeq();
    setPreset(id);
    setGraph(graphPreset(id));
    setParams(defaultParamsFromSchema(schemaForPreset(id)));
    if (id === 'weekly_predict_eval' && models[0]) {
      setParams((p) => ({ ...defaultParamsFromSchema(schemaForPreset(id)), model_id: models[0].id }));
    }
    setSelectedId(null);
    setConnectMode(false);
  };

  const addNode = useCallback((kind, at = null) => {
    const id = newNodeId(kind);
    const upstream = graph.nodes[graph.nodes.length - 1];
    let position = at || autoLayout(graph.nodes, graph.nodes.length);
    if (at) {
      position = { x: at.x - FLOW_NODE_W / 2, y: at.y - FLOW_NODE_H / 2 };
    } else {
      position = { x: 80 + graph.nodes.length * 240, y: 120 + (graph.nodes.length % 2) * 100 };
    }
    const node = {
      id,
      kind,
      params: defaultNodeParams(kind, upstream?.kind, upstream?.id),
      position,
    };
    setGraph((g) => ({ ...g, nodes: [...g.nodes, node] }));
    setSelectedId(id);
    setPreset('custom');
  }, [graph.nodes]);

  const removeNode = (id) => {
    setGraph((g) => ({
      nodes: g.nodes.filter((n) => n.id !== id),
      edges: g.edges.filter((e) => e.from !== id && e.to !== id),
    }));
    if (selectedId === id) setSelectedId(null);
  };

  const onMoveNode = useCallback((id, position) => {
    setGraph((g) => ({
      ...g,
      nodes: g.nodes.map((n) => (n.id === id ? { ...n, position } : n)),
    }));
    setPreset('custom');
  }, []);

  const onConnect = useCallback((from, to, when) => {
    setGraph((g) => {
      const exists = g.edges.some((e) => e.from === from && e.to === to && e.when === (when || 'always'));
      if (exists) return g;
      return { ...g, edges: [...g.edges, { from, to, when: when || 'always' }] };
    });
    setPreset('custom');
    setConnectMode(false);
  }, []);

  const insertOnEdge = useCallback((edgeIndex, kind) => {
    setGraph((g) => {
      const edge = g.edges[edgeIndex];
      if (!edge) return g;
      const fromN = g.nodes.find((n) => n.id === edge.from);
      const toN = g.nodes.find((n) => n.id === edge.to);
      if (!fromN || !toN) return g;
      const id = newNodeId(kind);
      const mx = ((fromN.position?.x || 0) + (toN.position?.x || 0)) / 2 + FLOW_NODE_W / 2;
      const my = ((fromN.position?.y || 0) + (toN.position?.y || 0)) / 2 + FLOW_NODE_H / 2;
      const node = {
        id,
        kind,
        params: defaultNodeParams(kind, fromN.kind, fromN.id),
        position: { x: Math.round(mx - FLOW_NODE_W / 2), y: Math.round(my) },
      };
      const edges = g.edges.filter((_, i) => i !== edgeIndex);
      edges.push({ from: edge.from, to: id, when: edge.when || 'always' });
      edges.push({ from: id, to: edge.to, when: 'always' });
      return { nodes: [...g.nodes, node], edges };
    });
    setPreset('custom');
  }, []);

  const removeEdge = (idx) => {
    setGraph((g) => ({ ...g, edges: g.edges.filter((_, i) => i !== idx) }));
    setPreset('custom');
  };

  const updateNodeParams = (nextParams) => {
    if (!selectedId) return;
    setGraph((g) => ({
      ...g,
      nodes: g.nodes.map((n) => (n.id === selectedId ? { ...n, params: nextParams } : n)),
    }));
    setPreset('custom');
  };

  const handleLaunch = () => {
    if (graph.nodes.some((n) => n.kind === 'predict') && !params.model_id) return;
    onLaunch({
      name: name.trim() || undefined,
      definition: compileGraphDefinition(graph, schema),
      params,
    });
  };

  const needsModel = graph.nodes.some((n) => n.kind === 'predict');
  const canLaunch = graph.nodes.length > 0 && (!needsModel || params.model_id);

  return (
    <div className="wf-flow-studio">
      <header className="wf-flow-topbar">
        <div className="wf-flow-topbar-left">
          <input
            className="wf-flow-name-input"
            placeholder="流程名称（可选）"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
          <div className="wf-flow-presets">
            {[
              ['daily_ng_curation', '每日捞图'],
              ['weekly_predict_eval', '每周评测'],
              ['branch_empty_notify', '分支示例'],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={`wf-flow-preset-chip${preset === id ? ' is-active' : ''}`}
                onClick={() => loadPreset(id)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="wf-flow-topbar-right">
          <select className="form-select wf-flow-when-select" value={edgeWhen} onChange={(e) => setEdgeWhen(e.target.value)} title="连线条件">
            {EDGE_WHEN.map((w) => (
              <option key={w.value} value={w.value}>{w.label}</option>
            ))}
          </select>
          <button
            type="button"
            className={`btn btn-sm${connectMode ? ' btn-primary' : ''}`}
            onClick={() => setConnectMode((v) => !v)}
          >
            {connectMode ? '连线中…' : '连线模式'}
          </button>
          <button type="button" className="btn btn-sm" onClick={() => setInspectorOpen((v) => !v)}>
            {inspectorOpen ? '收起面板' : '属性面板'}
          </button>
          <button type="button" className="btn btn-primary btn-sm" disabled={busy || !canLaunch} onClick={handleLaunch}>
            启动流程
          </button>
        </div>
      </header>

      <div className="wf-flow-workspace">
        <aside className="wf-flow-palette">
          <div className="wf-flow-palette-title">组件库</div>
          {PALETTE_GROUPS.map((grp) => {
            const items = stepKinds.filter((k) => k.group === grp.key);
            if (!items.length) return null;
            return (
              <div key={grp.key} className="wf-flow-palette-group">
                <div className="wf-flow-palette-label">{grp.label}</div>
                {items.map((k) => (
                  <div
                    key={k.kind}
                    role="button"
                    tabIndex={0}
                    className={`wf-flow-palette-item${draggingKind === k.kind ? ' is-dragging' : ''}`}
                    draggable
                    onDragStart={(e) => {
                      paletteDragRef.current = true;
                      e.dataTransfer.setData(WF_STEP_DRAG_MIME, k.kind);
                      e.dataTransfer.effectAllowed = 'copy';
                      setDraggingKind(k.kind);
                    }}
                    onDragEnd={() => {
                      setDraggingKind(null);
                      requestAnimationFrame(() => { paletteDragRef.current = false; });
                    }}
                    onClick={() => {
                      if (paletteDragRef.current) return;
                      addNode(k.kind);
                    }}
                    onKeyDown={(e) => { if (e.key === 'Enter') addNode(k.kind); }}
                    title={`${k.desc}（可拖到画布）`}
                  >
                    <span className="wf-flow-palette-grip" aria-hidden>⠿</span>
                    <span className="wf-flow-palette-icon" style={{ color: k.color }}>{k.icon}</span>
                    <span>{k.label}</span>
                  </div>
                ))}
              </div>
            );
          })}
          <p className="wf-flow-palette-hint">拖到画布添加 · 点击也可添加 · 拖端口连线</p>
        </aside>

        <div className="wf-flow-main">
          <WorkflowFlowCanvas
            graph={graph}
            selectedId={selectedId}
            onSelectNode={setSelectedId}
            onMoveNode={onMoveNode}
            onConnect={onConnect}
            onInsertOnEdge={insertOnEdge}
            onDropNode={(kind, pt) => addNode(kind, pt)}
            connectMode={connectMode}
            edgeWhen={edgeWhen}
          />
        </div>

        {inspectorOpen && (
          <aside className="wf-flow-inspector">
            <h4>属性</h4>
            {selectedNode ? (
              <>
                <p className="wf-flow-inspector-title">{stepMeta(selectedNode.kind).label}</p>
                <code className="wf-flow-inspector-id">{selectedNode.id}</code>
                <div className="wf-flow-inspector-actions">
                  <button type="button" className="btn btn-sm" onClick={() => removeNode(selectedId)}>删除节点</button>
                </div>
                <details open>
                  <summary>步骤参数</summary>
                  <textarea
                    className="wf-params-input"
                    rows={6}
                    value={JSON.stringify(selectedNode.params || {}, null, 2)}
                    onChange={(e) => {
                      try { updateNodeParams(JSON.parse(e.target.value || '{}')); } catch { /* */ }
                    }}
                  />
                </details>
              </>
            ) : (
              <p className="wf-muted">选中节点可编辑；从端口拖线或开连线模式</p>
            )}

            <h4>连线</h4>
            <ul className="wf-edge-list">
              {graph.edges.map((e, i) => (
                <li key={`${e.from}-${e.to}-${i}`}>
                  <code>{e.from}</code>→<code>{e.to}</code>
                  <span className="wf-edge-when">{EDGE_WHEN.find((w) => w.value === e.when)?.label || e.when}</span>
                  <button type="button" className="btn-link" onClick={() => removeEdge(i)}>删</button>
                </li>
              ))}
            </ul>

            <h4>运行参数</h4>
            <WorkflowParamsForm schema={schema} value={params} onChange={setParams} models={models} />
            {needsModel && !params.model_id && <p className="wf-composer-hint">含预测步骤需选模型</p>}
          </aside>
        )}
      </div>
    </div>
  );
}
