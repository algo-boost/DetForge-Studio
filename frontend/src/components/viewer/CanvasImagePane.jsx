import {
  forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState,
} from 'react';
import {
  ADJUST_DEFAULT,
  annTooltipLines,
  calcCenterOnBboxPanZoom,
  calcFitZoom,
  categoryColor,
  clientToImageCoords,
  hitTestAnnotationAt,
  imageAdjustFilter,
  passesConfThreshold,
} from '../../lib/viewerCanvas';

function drawHoverTooltip(ctx, rx, ry, rw, rh, lines, canvasW) {
  ctx.font = '12px system-ui, sans-serif';
  const lineH = 14;
  const pad = 6;
  const boxW = Math.max(...lines.map((l) => ctx.measureText(l).width)) + pad * 2;
  const boxH = lines.length * lineH + pad * 2;
  let tx = rx;
  let ty = ry - boxH - 4;
  if (ty < 0) ty = ry + rh + 4;
  if (tx + boxW > canvasW) tx = canvasW - boxW;
  if (tx < 0) tx = 4;
  ctx.fillStyle = 'rgba(0,0,0,0.88)';
  ctx.fillRect(tx, ty, boxW, boxH);
  ctx.strokeStyle = 'rgba(148, 163, 184, 0.6)';
  ctx.lineWidth = 1;
  ctx.strokeRect(tx, ty, boxW, boxH);
  ctx.fillStyle = '#fff';
  lines.forEach((line, i) => {
    ctx.fillText(line, tx + pad, ty + pad + (i + 1) * lineH - 2);
  });
}

/**
 * 单图 canvas：滚轮缩放、拖拽平移、预测框叠加（独立 zoom，不同步）。
 */
const CanvasImagePane = forwardRef(function CanvasImagePane({
  imageUrl,
  imageKey,
  annotations = [],
  showBoxes = true,
  showLabels = true,
  showBoxIndex = false,
  annFill = false,
  confOpacity = false,
  hiddenCats,
  hiddenAnnIndices,
  confThreshold = 0,
  lineWidth = 0.3,
  brightness = ADJUST_DEFAULT,
  contrast = ADJUST_DEFAULT,
  saturation = ADJUST_DEFAULT,
  applyImageAdjust = true,
  fitTick = 0,
  emptyHint = '无图片',
  boxStyle = 'pred',
  hoveredAnnIdx: hoveredAnnIdxProp,
  onHoverAnnIdx,
  onZoomChange,
}, ref) {
  const canvasRef = useRef(null);
  const imgRef = useRef(null);
  const containerRef = useRef(null);
  const dragRef = useRef(null);

  const [zoom, setZoom] = useState(0.5);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [imgLoaded, setImgLoaded] = useState(false);
  const [natural, setNatural] = useState({ w: 0, h: 0 });
  const [hoveredLocal, setHoveredLocal] = useState(null);

  const hiddenCatSet = hiddenCats instanceof Set ? hiddenCats : new Set();
  const hiddenIdxSet = hiddenAnnIndices instanceof Set ? hiddenAnnIndices : new Set();
  const hoveredAnnIdx = hoveredAnnIdxProp !== undefined ? hoveredAnnIdxProp : hoveredLocal;
  const setHoveredAnnIdx = onHoverAnnIdx || setHoveredLocal;

  useEffect(() => {
    onZoomChange?.(zoom);
  }, [zoom, onZoomChange]);

  const centerOnBbox = useCallback((bbox) => {
    const el = containerRef.current;
    const iw = natural.w;
    const ih = natural.h;
    const next = calcCenterOnBboxPanZoom(el, panX, panY, zoom, iw, ih, bbox);
    if (!next) return;
    setZoom(next.zoom);
    setPanX(next.panX);
    setPanY(next.panY);
  }, [natural.w, natural.h, panX, panY, zoom]);

  useImperativeHandle(ref, () => ({ centerOnBbox, getZoom: () => zoom }), [centerOnBbox, zoom]);

  const drawAnns = useCallback(() => {
    const canvas = canvasRef.current;
    const img = imgRef.current;
    if (!canvas || !img || img.naturalWidth === 0 || !showBoxes) return;
    const iw = natural.w || img.naturalWidth;
    const ih = natural.h || img.naturalHeight;
    const dw = iw * zoom;
    const dh = ih * zoom;
    canvas.width = dw;
    canvas.height = dh;
    canvas.style.width = `${dw}px`;
    canvas.style.height = `${dh}px`;
    const ctx = canvas.getContext('2d');
    const sx = dw / iw;
    const sy = dh / ih;
    ctx.clearRect(0, 0, dw, dh);
    const lw = Number(lineWidth) || 0.3;

    let visIdx = 0;
    annotations.forEach((ann, idx) => {
      if (!ann.bbox || hiddenCatSet.has(ann.category) || hiddenIdxSet.has(idx)) return;
      if (!passesConfThreshold(ann, confThreshold)) return;
      const [x, y, bw, bh] = ann.bbox;
      if (bw == null || bh == null) return;
      visIdx += 1;
      const rx = x * sx;
      const ry = y * sy;
      const rw = bw * sx;
      const rh = bh * sy;
      const isHovered = hoveredAnnIdx === idx;
      const color = categoryColor(ann.category);
      ctx.strokeStyle = color;
      ctx.lineWidth = Math.max(1, (isHovered ? lw + 0.2 : lw) * zoom * 4);
      if (boxStyle === 'pred') ctx.setLineDash([8, 4]);
      ctx.strokeRect(rx, ry, rw, rh);
      ctx.setLineDash([]);
      if (annFill) {
        ctx.fillStyle = `${color}22`;
        ctx.fillRect(rx, ry, rw, rh);
      }
      if (showLabels) {
        const idxLabel = showBoxIndex ? `#${visIdx} ` : '';
        const scorePart = ann.score != null ? ` ${(Number(ann.score) * 100).toFixed(1)}%` : '';
        const label = `${idxLabel}${ann.category || ''}${scorePart}`.trim();
        ctx.font = 'bold 11px system-ui, sans-serif';
        const lw2 = ctx.measureText(label).width + 8;
        const lh = 16;
        const lx = rx;
        const ly = ry > lh + 2 ? ry - lh - 2 : ry + 2;
        ctx.globalAlpha = confOpacity && ann.score != null
          ? Math.max(0.35, Number(ann.score))
          : 1;
        ctx.fillStyle = color;
        ctx.fillRect(lx, ly, lw2, lh);
        ctx.fillStyle = '#fff';
        ctx.fillText(label, lx + 4, ly + lh - 4);
        ctx.globalAlpha = 1;
      }
      if (isHovered) {
        drawHoverTooltip(ctx, rx, ry, rw, rh, annTooltipLines(ann), dw);
      }
    });
  }, [
    annotations, zoom, showBoxes, showLabels, showBoxIndex, annFill, confOpacity,
    hiddenCatSet, hiddenIdxSet, confThreshold, imgLoaded, natural, boxStyle, lineWidth,
    hoveredAnnIdx,
  ]);

  useEffect(() => { drawAnns(); }, [drawAnns]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return undefined;
    const onWheel = (e) => {
      if (!e.deltaY) return;
      e.preventDefault();
      e.stopPropagation();
      setZoom((z) => Math.max(0.01, Math.min(32, z * (e.deltaY < 0 ? 1.12 : 0.89))));
    };
    el.addEventListener('wheel', onWheel, { passive: false, capture: true });
    return () => el.removeEventListener('wheel', onWheel, { capture: true });
  }, []);

  const fitWindow = useCallback(() => {
    const el = containerRef.current;
    const img = imgRef.current;
    if (!el || !img?.naturalWidth) return;
    const z = calcFitZoom(el, img.naturalWidth, img.naturalHeight);
    setZoom(z > 0.01 ? z : 0.5);
    setPanX(0);
    setPanY(0);
  }, []);

  useEffect(() => {
    if (fitTick > 0) fitWindow();
  }, [fitTick, fitWindow]);

  const handleLoad = () => {
    const img = imgRef.current;
    if (!img) return;
    setNatural({ w: img.naturalWidth, h: img.naturalHeight });
    setImgLoaded(true);
    requestAnimationFrame(() => requestAnimationFrame(fitWindow));
  };

  useEffect(() => {
    setImgLoaded(false);
    setNatural({ w: 0, h: 0 });
    setPanX(0);
    setPanY(0);
    setHoveredAnnIdx(null);
    const t = setTimeout(() => {
      if (imgRef.current?.complete && imgRef.current.naturalWidth > 0) handleLoad();
    }, 80);
    return () => clearTimeout(t);
  }, [imageKey, imageUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  const pickAnnAtClient = useCallback((clientX, clientY) => {
    if (!showBoxes || !annotations.length) return -1;
    const el = containerRef.current;
    const { x: imgX, y: imgY } = clientToImageCoords(
      el, panX, panY, zoom, natural.w, natural.h, clientX, clientY,
    );
    const tol = Math.max(4, 6 / zoom);
    return hitTestAnnotationAt(annotations, imgX, imgY, {
      hiddenCats: hiddenCatSet,
      hiddenAnnIndices: hiddenIdxSet,
      confThreshold,
      borderOnly: false,
      tol,
    });
  }, [
    annotations, showBoxes, panX, panY, zoom, natural.w, natural.h,
    hiddenCatSet, hiddenIdxSet, confThreshold,
  ]);

  const filterStyle = applyImageAdjust
    ? imageAdjustFilter(brightness, contrast, saturation)
    : undefined;
  const iw = (natural.w || 1) * zoom;
  const ih = (natural.h || 1) * zoom;

  if (!imageUrl) {
    return (
      <div className="canvas-pane canvas-pane-empty">
        <div>{emptyHint}</div>
      </div>
    );
  }

  return (
    <div
      className="canvas-pane"
      ref={containerRef}
      onMouseDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        dragRef.current = { x: e.clientX, y: e.clientY, px: panX, py: panY };
      }}
      onMouseMove={(e) => {
        if (dragRef.current) {
          setPanX(dragRef.current.px + e.clientX - dragRef.current.x);
          setPanY(dragRef.current.py + e.clientY - dragRef.current.y);
          return;
        }
        if (showBoxes) {
          const hit = pickAnnAtClient(e.clientX, e.clientY);
          setHoveredAnnIdx(hit >= 0 ? hit : null);
        }
      }}
      onMouseUp={() => { dragRef.current = null; }}
      onMouseLeave={() => {
        dragRef.current = null;
        setHoveredAnnIdx(null);
      }}
    >
      <div
        className="canvas-pane-inner"
        style={{ left: `calc(50% + ${panX}px)`, top: `calc(50% + ${panY}px)` }}
      >
        <img
          ref={imgRef}
          src={imageUrl}
          alt=""
          draggable={false}
          style={{ width: iw, height: ih, display: 'block', filter: filterStyle }}
          onLoad={handleLoad}
        />
        {showBoxes && (
          <canvas ref={canvasRef} className="canvas-pane-overlay" style={{ width: iw, height: ih }} />
        )}
      </div>
      <div className="canvas-pane-zoom-badge">{Math.round(zoom * 100)}%</div>
    </div>
  );
});

export default CanvasImagePane;

/** 供父组件触发适应窗口 */
export function usePaneFitTrigger() {
  const [tick, setTick] = useState(0);
  return { fitTick: tick, requestFit: () => setTick((t) => t + 1) };
}
