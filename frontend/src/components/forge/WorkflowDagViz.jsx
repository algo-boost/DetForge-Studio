import { EDGE_WHEN } from '../../lib/workflowGraph';
import { stepMeta } from '../../lib/workflowCatalog';

const NODE_W = 148;
const NODE_H = 72;

function whenLabel(w) {
  return EDGE_WHEN.find((x) => x.value === w)?.label || w || '始终';
}

/**
 * DAG 画布：节点 + SVG 连线（含分支条件标签）
 */
export default function WorkflowDagViz({
  graph,
  stepStatus = {},
  selectedId = null,
  onSelectNode,
  interactive = false,
}) {
  if (!graph?.nodes?.length) {
    return <p className="wf-viz-empty">拖入或添加步骤以设计流程</p>;
  }

  const nodes = graph.nodes;
  const edges = graph.edges || [];
  const maxX = Math.max(...nodes.map((n) => (n.position?.x || 0) + NODE_W), 400);
  const maxY = Math.max(...nodes.map((n) => (n.position?.y || 0) + NODE_H), 280);

  const center = (n) => ({
    x: (n.position?.x || 0) + NODE_W / 2,
    y: (n.position?.y || 0) + NODE_H / 2,
  });

  return (
    <div className="wf-dag-viz" style={{ minWidth: maxX + 40, minHeight: maxY + 40 }}>
      <svg className="wf-dag-edges" width={maxX + 40} height={maxY + 40}>
        <defs>
          <marker id="wf-arrow" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
            <path d="M0,0 L6,3 L0,6 Z" fill="var(--text-muted)" />
          </marker>
        </defs>
        {edges.map((e, i) => {
          const from = nodes.find((n) => n.id === e.from);
          const to = nodes.find((n) => n.id === e.to);
          if (!from || !to) return null;
          const a = center(from);
          const b = center(to);
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2;
          const isBranch = e.when && e.when !== 'always';
          return (
            <g key={`${e.from}-${e.to}-${i}`}>
              <line
                x1={a.x + NODE_W / 2 - 10}
                y1={a.y}
                x2={b.x - NODE_W / 2 + 10}
                y2={b.y}
                stroke={isBranch ? '#f59e0b' : 'var(--border)'}
                strokeWidth={isBranch ? 2 : 1.5}
                markerEnd="url(#wf-arrow)"
              />
              {isBranch && (
                <text x={mx} y={my - 6} className="wf-dag-edge-label" textAnchor="middle">
                  {whenLabel(e.when)}
                </text>
              )}
            </g>
          );
        })}
      </svg>
      <div className="wf-dag-nodes">
        {nodes.map((n) => {
          const meta = stepMeta(n.kind);
          const st = stepStatus[n.id];
          const sel = selectedId === n.id;
          return (
            <button
              key={n.id}
              type="button"
              className={`wf-dag-node wf-dag-node-${st || 'default'}${sel ? ' is-selected' : ''}`}
              style={{
                left: n.position?.x || 0,
                top: n.position?.y || 0,
                '--wf-node-color': meta.color,
              }}
              onClick={interactive && onSelectNode ? () => onSelectNode(n.id) : undefined}
              disabled={!interactive}
              title={meta.desc}
            >
              <span className="wf-dag-node-icon">{meta.icon}</span>
              <span className="wf-dag-node-label">{meta.label}</span>
              <span className="wf-dag-node-id">{n.id}</span>
              {st && <span className={`wf-dag-node-st wf-viz-st-${st}`}>{st}</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
