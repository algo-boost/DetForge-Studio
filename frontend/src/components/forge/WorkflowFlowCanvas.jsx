import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { stepMeta } from '../../lib/workflowCatalog';
import { EDGE_WHEN, WF_STEP_DRAG_MIME, listStepKinds } from '../../lib/workflowGraph';
import {
  FLOW_NODE_H,
  FLOW_NODE_W,
  bezierPath,
  edgeMidpoint,
  graphBounds,
  nodePorts,
} from '../../lib/workflowFlowGeometry';

function whenLabel(w) {
  return EDGE_WHEN.find((x) => x.value === w)?.label || w || '始终';
}

function StepIcon({ kind, color }) {
  const meta = stepMeta(kind);
  return (
    <span className="wf-flow-node-icon" style={{ background: `${color || meta.color}18`, color: color || meta.color }}>
      {meta.icon}
    </span>
  );
}

/**
 * LangFlow 风格画布：点阵底、可拖拽节点、贝塞尔连线、端口拖连、边中点 +、小地图
 */
export default function WorkflowFlowCanvas({
  graph,
  stepStatus = {},
  selectedId = null,
  onSelectNode,
  onMoveNode,
  onConnect,
  onInsertOnEdge,
  onDropNode,
  connectMode = false,
  edgeWhen = 'always',
  readOnly = false,
}) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [drag, setDrag] = useState(null);
  const [linkDrag, setLinkDrag] = useState(null);
  const [panDrag, setPanDrag] = useState(null);
  const [insertMenu, setInsertMenu] = useState(null);
  const [dropOver, setDropOver] = useState(false);

  const nodes = graph?.nodes || [];
  const edges = graph?.edges || [];
  const bounds = useMemo(() => graphBounds(nodes), [nodes]);

  const canvasW = Math.max(bounds.width, 900);
  const canvasH = Math.max(bounds.height, 520);

  const clientToCanvas = useCallback((clientX, clientY) => {
    const el = canvasRef.current || wrapRef.current;
    if (!el) return { x: 0, y: 0 };
    const r = el.getBoundingClientRect();
    return {
      x: (clientX - r.left - pan.x) / zoom,
      y: (clientY - r.top - pan.y) / zoom,
    };
  }, [pan, zoom]);

  const onCanvasDragOver = useCallback((e) => {
    if (readOnly || !onDropNode) return;
    if (!e.dataTransfer.types.includes(WF_STEP_DRAG_MIME)) return;
    e.preventDefault();
    e.dataTransfer.dropEffect = 'copy';
    setDropOver(true);
  }, [readOnly, onDropNode]);

  const onCanvasDragLeave = useCallback((e) => {
    if (!canvasRef.current?.contains(e.relatedTarget)) {
      setDropOver(false);
    }
  }, []);

  const onCanvasDrop = useCallback((e) => {
    if (readOnly || !onDropNode) return;
    e.preventDefault();
    setDropOver(false);
    const kind = e.dataTransfer.getData(WF_STEP_DRAG_MIME);
    if (!kind) return;
    const pt = clientToCanvas(e.clientX, e.clientY);
    onDropNode(kind, pt);
  }, [readOnly, onDropNode, clientToCanvas]);

  useEffect(() => {
    const onMove = (e) => {
      if (drag) {
        const dx = (e.clientX - drag.x0) / zoom;
        const dy = (e.clientY - drag.y0) / zoom;
        onMoveNode?.(drag.id, {
          x: Math.round(drag.nx + dx),
          y: Math.round(drag.ny + dy),
        });
      } else if (linkDrag) {
        setLinkDrag((ld) => (ld ? { ...ld, cx: e.clientX, cy: e.clientY } : null));
      } else if (panDrag) {
        setPan({
          x: panDrag.px + (e.clientX - panDrag.x0),
          y: panDrag.py + (e.clientY - panDrag.y0),
        });
      }
    };
    const onUp = (e) => {
      if (linkDrag && onConnect) {
        const pt = clientToCanvas(e.clientX, e.clientY);
        const target = nodes.find((n) => {
          const p = nodePorts(n).input;
          return Math.hypot(p.x - pt.x, p.y - pt.y) < 28;
        });
        if (target && target.id !== linkDrag.fromId) {
          onConnect(linkDrag.fromId, target.id, linkDrag.when);
        }
      }
      setDrag(null);
      setLinkDrag(null);
      setPanDrag(null);
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [drag, linkDrag, panDrag, zoom, nodes, onMoveNode, onConnect, clientToCanvas, linkDrag?.when]);

  const onNodePointerDown = (e, node) => {
    if (readOnly) {
      e.stopPropagation();
      onSelectNode?.(node.id);
      return;
    }
    e.stopPropagation();
    if (connectMode) {
      onSelectNode?.(node.id);
      return;
    }
    setDrag({
      id: node.id,
      x0: e.clientX,
      y0: e.clientY,
      nx: node.position?.x || 0,
      ny: node.position?.y || 0,
    });
    onSelectNode?.(node.id);
  };

  const onOutputPortDown = (e, node) => {
    if (readOnly) return;
    e.stopPropagation();
    const p = nodePorts(node).output;
    setLinkDrag({
      fromId: node.id,
      sx: p.x,
      sy: p.y,
      cx: e.clientX,
      cy: e.clientY,
      when: edgeWhen,
    });
  };

  const onCanvasPointerDown = (e) => {
    if (e.target !== e.currentTarget && !e.target.classList.contains('wf-flow-canvas-inner')) return;
    if (readOnly) return;
    setPanDrag({ x0: e.clientX, y0: e.clientY, px: pan.x, py: pan.y });
    onSelectNode?.(null);
    setInsertMenu(null);
  };

  const linkPreview = linkDrag && wrapRef.current ? (() => {
    const r = wrapRef.current.getBoundingClientRect();
    const ex = (linkDrag.cx - r.left - pan.x) / zoom;
    const ey = (linkDrag.cy - r.top - pan.y) / zoom;
    return bezierPath({ x: linkDrag.sx, y: linkDrag.sy }, { x: ex, y: ey });
  })() : null;

  return (
    <div className="wf-flow-canvas-wrap" ref={wrapRef}>
      <div className="wf-flow-zoom-bar">
        <button type="button" className="wf-flow-zoom-btn" onClick={() => setZoom((z) => Math.min(1.5, z + 0.1))}>+</button>
        <span>{Math.round(zoom * 100)}%</span>
        <button type="button" className="wf-flow-zoom-btn" onClick={() => setZoom((z) => Math.max(0.5, z - 0.1))}>−</button>
        <button type="button" className="wf-flow-zoom-btn" onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>重置</button>
      </div>

      <div
        ref={canvasRef}
        className={`wf-flow-canvas${dropOver ? ' is-drop-target' : ''}`}
        onPointerDown={onCanvasPointerDown}
        onDragOver={onCanvasDragOver}
        onDragLeave={onCanvasDragLeave}
        onDrop={onCanvasDrop}
        role="presentation"
      >
        {!nodes.length && !readOnly && (
          <div className="wf-flow-empty-hint">
            从左侧组件库<strong>拖拽</strong>组件到此处
          </div>
        )}
        <div
          className="wf-flow-canvas-inner"
          style={{
            width: canvasW,
            height: canvasH,
            transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
            transformOrigin: '0 0',
          }}
        >
          <svg className="wf-flow-edges" width={canvasW} height={canvasH}>
            <defs>
              <marker id="wf-flow-arrow" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 Z" fill="#60a5fa" />
              </marker>
              <marker id="wf-flow-arrow-branch" markerWidth="10" markerHeight="10" refX="8" refY="5" orient="auto">
                <path d="M0,0 L10,5 L0,10 Z" fill="#f59e0b" />
              </marker>
            </defs>
            {edges.map((e, i) => {
              const from = nodes.find((n) => n.id === e.from);
              const to = nodes.find((n) => n.id === e.to);
              if (!from || !to) return null;
              const a = nodePorts(from).output;
              const b = nodePorts(to).input;
              const path = bezierPath(a, b);
              const mid = edgeMidpoint(a, b);
              const isBranch = e.when && e.when !== 'always';
              return (
                <g key={`${e.from}-${e.to}-${i}`} className="wf-flow-edge-g">
                  <path
                    d={path}
                    className={`wf-flow-edge${isBranch ? ' is-branch' : ''}`}
                    markerEnd={isBranch ? 'url(#wf-flow-arrow-branch)' : 'url(#wf-flow-arrow)'}
                  />
                  {isBranch && (
                    <text x={mid.x} y={mid.y - 10} className="wf-flow-edge-label" textAnchor="middle">
                      {whenLabel(e.when)}
                    </text>
                  )}
                  {!readOnly && onInsertOnEdge && (
                    <g
                      className="wf-flow-edge-plus"
                      transform={`translate(${mid.x}, ${mid.y})`}
                      onPointerDown={(ev) => ev.stopPropagation()}
                      onClick={(ev) => {
                        ev.stopPropagation();
                        setInsertMenu({ edgeIndex: i, x: mid.x, y: mid.y, edge: e });
                      }}
                    >
                      <circle r="11" className="wf-flow-edge-plus-bg" />
                      <text textAnchor="middle" dy="4" className="wf-flow-edge-plus-t">+</text>
                    </g>
                  )}
                </g>
              );
            })}
            {linkPreview && (
              <path d={linkPreview} className="wf-flow-edge is-drafting" />
            )}
          </svg>

          {insertMenu && onInsertOnEdge && (
            <div
              className="wf-flow-insert-menu"
              style={{ left: insertMenu.x, top: insertMenu.y + 16 }}
              onPointerDown={(ev) => ev.stopPropagation()}
            >
              <div className="wf-flow-insert-menu-head">
                <span>插入步骤</span>
                <button type="button" className="btn-link" onClick={() => setInsertMenu(null)}>×</button>
              </div>
              {listStepKinds().map((k) => (
                <button
                  key={k.kind}
                  type="button"
                  className="wf-flow-insert-opt"
                  onClick={() => {
                    onInsertOnEdge(insertMenu.edgeIndex, k.kind);
                    setInsertMenu(null);
                  }}
                >
                  {k.icon} {k.label}
                </button>
              ))}
            </div>
          )}

          {nodes.map((n) => {
            const meta = stepMeta(n.kind);
            const st = stepStatus[n.id];
            const sel = selectedId === n.id;
            const x = n.position?.x || 0;
            const y = n.position?.y || 0;
            return (
              <div
                key={n.id}
                className={`wf-flow-node${sel ? ' is-selected' : ''}${st ? ` is-status-${st}` : ''}`}
                style={{ left: x, top: y, width: FLOW_NODE_W, height: FLOW_NODE_H }}
                onPointerDown={(e) => onNodePointerDown(e, n)}
                onClick={(e) => {
                  e.stopPropagation();
                  if (connectMode && onConnect && selectedId && selectedId !== n.id) {
                    onConnect(selectedId, n.id, edgeWhen);
                  } else {
                    onSelectNode?.(n.id);
                  }
                }}
                role="button"
                tabIndex={0}
              >
                {!readOnly && <span className="wf-flow-port wf-flow-port-in" title="输入" />}
                <StepIcon kind={n.kind} color={meta.color} />
                <div className="wf-flow-node-text">
                  <span className="wf-flow-node-title">{meta.label}</span>
                  <span className="wf-flow-node-sub">{n.id}</span>
                </div>
                {st && <span className={`wf-flow-node-badge wf-viz-st-${st}`}>{st}</span>}
                {!readOnly && (
                  <span
                    className="wf-flow-port wf-flow-port-out"
                    title="拖出连线"
                    onPointerDown={(e) => onOutputPortDown(e, n)}
                  />
                )}
              </div>
            );
          })}
        </div>
      </div>

      <div className="wf-flow-minimap" aria-hidden>
        <svg viewBox={`${bounds.minX - 20} ${bounds.minY - 20} ${bounds.width} ${bounds.height}`}>
          {edges.map((e, i) => {
            const from = nodes.find((n) => n.id === e.from);
            const to = nodes.find((n) => n.id === e.to);
            if (!from || !to) return null;
            const fx = (from.position?.x || 0) + FLOW_NODE_W / 2;
            const fy = (from.position?.y || 0) + FLOW_NODE_H / 2;
            const tx = (to.position?.x || 0) + FLOW_NODE_W / 2;
            const ty = (to.position?.y || 0) + FLOW_NODE_H / 2;
            return <line key={i} x1={fx} y1={fy} x2={tx} y2={ty} stroke="#94a3b8" strokeWidth="2" />;
          })}
          {nodes.map((n) => (
            <rect
              key={n.id}
              x={n.position?.x || 0}
              y={n.position?.y || 0}
              width={FLOW_NODE_W}
              height={FLOW_NODE_H}
              rx="4"
              fill={selectedId === n.id ? '#3b82f6' : '#cbd5e1'}
              opacity="0.85"
            />
          ))}
        </svg>
      </div>
    </div>
  );
}
