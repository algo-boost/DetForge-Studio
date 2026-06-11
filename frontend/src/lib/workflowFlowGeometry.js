/** 工作流画布几何与连线 */

export const FLOW_NODE_W = 200;
export const FLOW_NODE_H = 72;

export function nodePorts(node) {
  const x = node?.position?.x || 0;
  const y = node?.position?.y || 0;
  return {
    input: { x, y: y + FLOW_NODE_H / 2 },
    output: { x: x + FLOW_NODE_W, y: y + FLOW_NODE_H / 2 },
  };
}

export function bezierPath(a, b) {
  const dx = Math.max(40, Math.abs(b.x - a.x) * 0.45);
  return `M ${a.x} ${a.y} C ${a.x + dx} ${a.y}, ${b.x - dx} ${b.y}, ${b.x} ${b.y}`;
}

export function edgeMidpoint(a, b) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

export function graphBounds(nodes = []) {
  if (!nodes.length) {
    return { minX: 0, minY: 0, width: 900, height: 520 };
  }
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const n of nodes) {
    const x = n.position?.x || 0;
    const y = n.position?.y || 0;
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x + FLOW_NODE_W);
    maxY = Math.max(maxY, y + FLOW_NODE_H);
  }
  const pad = 80;
  return {
    minX: minX - pad,
    minY: minY - pad,
    width: maxX - minX + pad * 2,
    height: maxY - minY + pad * 2,
  };
}
