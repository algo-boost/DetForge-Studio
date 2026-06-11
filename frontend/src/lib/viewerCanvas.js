/** 样本图库 Canvas 绘制与交互辅助 */

export const ADJUST_DEFAULT = { brightness: 100, contrast: 100, saturation: 100 };
export const BRIGHTNESS_MIN = 50;
export const BRIGHTNESS_MAX = 150;
export const VIEWER_PALETTE = ['#ef4444', '#3b82f6', '#22c55e', '#f59e0b', '#a855f7', '#06b6d4'];

export function categoryColor(categoryId) {
  const n = Math.abs(parseInt(categoryId, 10) || String(categoryId || '').length);
  return VIEWER_PALETTE[n % VIEWER_PALETTE.length];
}

export function lineWidthOptions() {
  return [1, 2, 3, 4, 6];
}

export function passesConfThreshold(annotation, threshold = 0) {
  const score = annotation?.score ?? annotation?.confidence ?? 1;
  return score >= threshold;
}

export function annTooltipLines(annotation) {
  if (!annotation) return [];
  const lines = [];
  if (annotation.category_name || annotation.category_id != null) {
    lines.push(String(annotation.category_name || annotation.category_id));
  }
  if (annotation.score != null) lines.push(`score: ${annotation.score}`);
  return lines.length ? lines : ['annotation'];
}

export function calcFitZoom(imageW, imageH, viewW, viewH, padding = 16) {
  if (!imageW || !imageH || !viewW || !viewH) return 1;
  const zw = (viewW - padding * 2) / imageW;
  const zh = (viewH - padding * 2) / imageH;
  return Math.min(zw, zh, 1);
}

export function calcCenterOnBboxPanZoom(bbox, imageSize, viewSize, currentZoom = 1) {
  const [x, y, w, h] = bbox || [0, 0, 0, 0];
  const cx = x + w / 2;
  const cy = y + h / 2;
  const zoom = currentZoom;
  return {
    zoom,
    panX: (viewSize?.width || 0) / 2 - cx * zoom,
    panY: (viewSize?.height || 0) / 2 - cy * zoom,
  };
}

export function clientToImageCoords(clientX, clientY, rect, pan, zoom) {
  const x = (clientX - (rect?.left || 0) - (pan?.x || 0)) / (zoom || 1);
  const y = (clientY - (rect?.top || 0) - (pan?.y || 0)) / (zoom || 1);
  return { x, y };
}

export function hitTestAnnotationAt(x, y, annotations = [], threshold = 6) {
  for (let i = annotations.length - 1; i >= 0; i -= 1) {
    const ann = annotations[i];
    const bbox = ann?.bbox || ann?.bbox_xywh;
    if (!bbox || bbox.length < 4) continue;
    const [bx, by, bw, bh] = bbox;
    if (x >= bx - threshold && x <= bx + bw + threshold && y >= by - threshold && y <= by + bh + threshold) {
      return ann;
    }
  }
  return null;
}

export function imageAdjustFilter(adjust = ADJUST_DEFAULT) {
  const b = adjust?.brightness ?? 100;
  const c = adjust?.contrast ?? 100;
  const s = adjust?.saturation ?? 100;
  return `brightness(${b}%) contrast(${c}%) saturate(${s}%)`;
}
