import { useEffect, useMemo, useRef, useState } from 'react';
import { resolveItemImageSrc } from '../../lib/resultImage';
import {
  ADJUST_DEFAULT,
  BRIGHTNESS_MAX,
  BRIGHTNESS_MIN,
  categoryColor,
  lineWidthOptions,
  passesConfThreshold,
  VIEWER_PALETTE,
} from '../../lib/viewerCanvas';
import { isResultNg, resultStatusLabel } from '../InspectionResultsLayout';
import CanvasImagePane, { usePaneFitTrigger } from './CanvasImagePane';

function VBtn({ active, onClass = 'is-on-blue', offClass = 'is-off', title, onClick, disabled, children }) {
  return (
    <button
      type="button"
      className={`mqc-vbtn${active ? ` ${onClass}` : ` ${offClass}`}`}
      title={title}
      onClick={onClick}
      disabled={disabled}
    >
      {children}
    </button>
  );
}

export default function DualCompareViewer({
  customerUrl,
  platformItem,
  noMatch,
  lookupBusy,
  activeIndex,
  totalCount,
  onNav,
}) {
  const [showBoxes, setShowBoxes] = useState(true);
  const [showLabels, setShowLabels] = useState(true);
  const [showBoxIndex, setShowBoxIndex] = useState(false);
  const [annFill, setAnnFill] = useState(false);
  const [confOpacity, setConfOpacity] = useState(false);
  const [hiddenCats, setHiddenCats] = useState(() => new Set());
  const [hiddenAnnIndices, setHiddenAnnIndices] = useState(() => new Set());
  const [hoveredAnnIdx, setHoveredAnnIdx] = useState(null);
  const [confThreshold, setConfThreshold] = useState(0);
  const [lineWidth, setLineWidth] = useState(0.3);
  const [brightness, setBrightness] = useState(ADJUST_DEFAULT);
  const [contrast, setContrast] = useState(ADJUST_DEFAULT);
  const [saturation, setSaturation] = useState(ADJUST_DEFAULT);

  const platPaneRef = useRef(null);
  const custFit = usePaneFitTrigger();
  const platFit = usePaneFitTrigger();
  const [custZoomPct, setCustZoomPct] = useState(50);
  const [platZoomPct, setPlatZoomPct] = useState(50);

  const platformUrl = platformItem ? resolveItemImageSrc(platformItem, 'detail') : '';
  const imageKey = `${platformItem?.id || 'none'}`;
  const annList = platformItem?.annotations || [];

  const categories = useMemo(() => {
    const s = new Set();
    annList.forEach((a) => { if (a.category) s.add(a.category); });
    return [...s].sort((a, b) => String(a).localeCompare(String(b), 'zh-CN'));
  }, [annList]);

  const annListItems = useMemo(() => {
    const items = [];
    annList.forEach((ann, idx) => {
      if (!ann.bbox) return;
      const filtered = hiddenCats.has(ann.category)
        || !passesConfThreshold(ann, confThreshold);
      items.push({ ann, idx, filtered });
    });
    return items;
  }, [annList, hiddenCats, confThreshold]);

  const visibleCount = useMemo(() => annList.filter((a, idx) => {
    if (!a.bbox || hiddenCats.has(a.category) || hiddenAnnIndices.has(idx)) return false;
    if (!passesConfThreshold(a, confThreshold)) return false;
    return true;
  }).length, [annList, hiddenCats, hiddenAnnIndices, confThreshold]);

  const toggleCat = (cat) => {
    setHiddenCats((prev) => {
      const n = new Set(prev);
      if (n.has(cat)) n.delete(cat); else n.add(cat);
      return n;
    });
  };

  const toggleAnnHidden = (idx, e) => {
    e?.stopPropagation();
    setHiddenAnnIndices((prev) => {
      const n = new Set(prev);
      if (n.has(idx)) n.delete(idx); else n.add(idx);
      return n;
    });
  };

  const resetAdjust = () => {
    setBrightness(ADJUST_DEFAULT);
    setContrast(ADJUST_DEFAULT);
    setSaturation(ADJUST_DEFAULT);
  };

  useEffect(() => {
    setHiddenAnnIndices(new Set());
    setHoveredAnnIdx(null);
  }, [imageKey]);

  const lwOpts = lineWidthOptions();

  return (
    <div className="mqc-viz-studio">
      <div className="mqc-viz-header">
        <span className="mqc-viz-header-title">对照看图</span>

        <div className="mqc-viz-adjust" title="仅作用于平台检测图，客户图保持原图">
          <span className="mqc-viz-adjust-tag">平台图</span>
          <label>
            亮度
            <input
              type="range"
              min={BRIGHTNESS_MIN}
              max={BRIGHTNESS_MAX}
              value={brightness}
              onChange={(e) => setBrightness(
                Math.min(BRIGHTNESS_MAX, Math.max(BRIGHTNESS_MIN, Number(e.target.value))),
              )}
            />
            <span className="mqc-viz-adjust-val">{brightness}%</span>
          </label>
          <label>
            对比
            <input
              type="range"
              min={50}
              max={200}
              value={contrast}
              onChange={(e) => setContrast(Number(e.target.value))}
            />
            <span className="mqc-viz-adjust-val">{contrast}%</span>
          </label>
          <label>
            饱和
            <input
              type="range"
              min={0}
              max={200}
              value={saturation}
              onChange={(e) => setSaturation(Number(e.target.value))}
            />
            <span className="mqc-viz-adjust-val">{saturation}%</span>
          </label>
          <button type="button" className="mqc-vbtn is-off" onClick={resetAdjust} title="重置平台图调整">
            重置
          </button>
        </div>

        <div className="mqc-viz-tools">
          <div className="mqc-viz-group">
            <span className="mqc-viz-hint" style={{ padding: '0 4px' }}>线宽</span>
            <select
              className="mqc-viz-linewidth"
              value={lineWidth}
              onChange={(e) => setLineWidth(Number(e.target.value))}
            >
              {lwOpts.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          </div>
          <div className="mqc-viz-group">
            <VBtn active={showBoxes} onClass="is-on-blue" title="预测框" onClick={() => setShowBoxes((v) => !v)}>框</VBtn>
            <VBtn active={showLabels} onClass="is-on-green" title="类别与置信度标签" onClick={() => setShowLabels((v) => !v)}>Aa</VBtn>
            <VBtn active={showBoxIndex} onClass="is-on-yellow" title="序号" onClick={() => setShowBoxIndex((v) => !v)}>#</VBtn>
            <VBtn active={annFill} onClass="is-on-cyan" title="半透明填充" onClick={() => setAnnFill((v) => !v)}>▦</VBtn>
            <VBtn active={confOpacity} onClass="is-on-purple" title="置信度透明" onClick={() => setConfOpacity((v) => !v)}>∿</VBtn>
          </div>
          <div className="mqc-viz-group">
            <span className="mqc-viz-hint">score≥</span>
            <input
              type="number"
              className="mqc-viz-conf-inp"
              min={0}
              max={1}
              step={0.05}
              value={confThreshold}
              onChange={(e) => setConfThreshold(Number(e.target.value) || 0)}
            />
          </div>
          <span className="mqc-viz-hint">悬停框显示详情 · 滚轮缩放 · 左右独立</span>
        </div>
      </div>

      <div className="mqc-viz-body">
        <div className="mqc-viz-pane">
          <div className="mqc-viz-pane-bar mqc-viz-pane-bar--customer">
            <span className="mqc-viz-pane-title">客户图</span>
            <span className="mqc-viz-pane-note">原图，不做亮度调整</span>
            <div className="mqc-viz-pane-zoom">
              <VBtn title="适应窗口" onClick={custFit.requestFit}>⊡</VBtn>
              <span className="mqc-viz-pane-zoom-pct">{custZoomPct}%</span>
            </div>
          </div>
          <div className="mqc-viz-pane-canvas">
            <CanvasImagePane
              imageUrl={customerUrl}
              imageKey={`cust-${customerUrl || 'x'}`}
              showBoxes={false}
              applyImageAdjust={false}
              fitTick={custFit.fitTick}
              emptyHint="无客户图"
              onZoomChange={(z) => setCustZoomPct(Math.round(z * 100))}
            />
          </div>
        </div>

        <div className={`mqc-viz-pane mqc-viz-pane--with-rail${noMatch ? ' is-muted' : ''}`}>
          <div className="mqc-viz-pane-bar mqc-viz-pane-bar--platform">
            <span className="mqc-viz-pane-title">平台检测图</span>
            {platformItem && (
              <span className="mqc-viz-pane-meta">
                #{platformItem.id}
                {platformItem.product_type ? ` · ${platformItem.product_type}` : ''}
                {' · '}
                <span className={isResultNg(platformItem) ? 'detail-status-ng' : 'detail-status-ok'}>
                  {resultStatusLabel(platformItem.check_status)}
                </span>
                {showBoxes && (
                  <span className="mqc-viz-pane-boxcnt">
                    {' · 框 '}{visibleCount}/{annList.length}
                  </span>
                )}
              </span>
            )}
            {!noMatch && totalCount > 0 && (
              <div className="mqc-viz-pane-zoom">
                <button type="button" className="mqc-vbtn is-off" disabled={activeIndex <= 0} onClick={() => onNav(-1)} title="上一张">‹</button>
                <span className="mqc-viz-pane-zoom-pct" style={{ minWidth: 36 }}>
                  {activeIndex + 1}/{totalCount}
                </span>
                <button type="button" className="mqc-vbtn is-off" disabled={activeIndex >= totalCount - 1} onClick={() => onNav(1)} title="下一张">›</button>
                <VBtn title="适应窗口" onClick={platFit.requestFit}>⊡</VBtn>
                <span className="mqc-viz-pane-zoom-pct">{platZoomPct}%</span>
              </div>
            )}
          </div>
          <div className="mqc-viz-pane-split">
            <div className="mqc-viz-pane-canvas">
              {noMatch ? (
                <div className="canvas-pane canvas-pane-empty">
                  <div>已标记：拍不到 / 找不到</div>
                </div>
              ) : platformItem ? (
                <CanvasImagePane
                  ref={platPaneRef}
                  imageUrl={platformUrl}
                  imageKey={imageKey}
                  annotations={annList}
                  showBoxes={showBoxes}
                  showLabels={showLabels}
                  showBoxIndex={showBoxIndex}
                  annFill={annFill}
                  confOpacity={confOpacity}
                  hiddenCats={hiddenCats}
                  hiddenAnnIndices={hiddenAnnIndices}
                  confThreshold={confThreshold}
                  lineWidth={lineWidth}
                  brightness={brightness}
                  contrast={contrast}
                  saturation={saturation}
                  applyImageAdjust
                  fitTick={platFit.fitTick}
                  hoveredAnnIdx={hoveredAnnIdx}
                  onHoverAnnIdx={setHoveredAnnIdx}
                  emptyHint={lookupBusy ? '查图中…' : '无图片'}
                  boxStyle="pred"
                  onZoomChange={(z) => setPlatZoomPct(Math.round(z * 100))}
                />
              ) : (
                <div className="canvas-pane canvas-pane-empty">
                  <div>{lookupBusy ? '查图中…' : '请选择候选图'}</div>
                </div>
              )}
            </div>

            {showBoxes && platformItem && annListItems.length > 0 && !noMatch && (
              <aside className="mqc-viz-ann-rail">
                <div className="mqc-viz-ann-rail-head">
                  <span>预测框 ({visibleCount}/{annList.length})</span>
                  <button
                    type="button"
                    className="mqc-vbtn is-off"
                    style={{ padding: '0 6px', fontSize: 10 }}
                    onClick={() => setHiddenAnnIndices(new Set())}
                  >
                    全部显示
                  </button>
                  <button
                    type="button"
                    className="mqc-vbtn is-off"
                    style={{ padding: '0 6px', fontSize: 10 }}
                    onClick={() => {
                      const all = new Set(annList.map((_, i) => i));
                      setHiddenAnnIndices(all);
                    }}
                  >
                    全部隐藏
                  </button>
                </div>
                {categories.length > 0 && (
                  <div className="mqc-viz-ann-cats">
                    {categories.map((cat) => {
                      const hidden = hiddenCats.has(cat);
                      return (
                        <button
                          key={cat}
                          type="button"
                          className={`mqc-viz-cat-chip mqc-viz-cat-chip--compact${hidden ? ' is-hidden' : ''}`}
                          onClick={() => toggleCat(cat)}
                          title={hidden ? '显示类别' : '隐藏类别'}
                        >
                          <span className="mqc-viz-cat-dot" style={{ background: categoryColor(cat, VIEWER_PALETTE) }} />
                          {cat}
                        </button>
                      );
                    })}
                  </div>
                )}
                <div className="mqc-viz-ann-list">
                  {annListItems.map(({ ann, idx, filtered }) => {
                    const hidden = hiddenAnnIndices.has(idx);
                    const isHovered = hoveredAnnIdx === idx;
                    const color = categoryColor(ann.category, VIEWER_PALETTE);
                    return (
                      <div
                        key={idx}
                        role="button"
                        tabIndex={0}
                        className={`mqc-viz-ann-item${hidden || filtered ? ' is-hidden' : ''}${isHovered ? ' is-hovered' : ''}`}
                        style={{ borderLeftColor: color }}
                        onClick={() => {
                          if (hidden || filtered) return;
                          platPaneRef.current?.centerOnBbox(ann.bbox);
                        }}
                        onMouseEnter={() => setHoveredAnnIdx(idx)}
                        onMouseLeave={() => setHoveredAnnIdx(null)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter' && !hidden && !filtered) {
                            platPaneRef.current?.centerOnBbox(ann.bbox);
                          }
                        }}
                      >
                        <span className="mqc-viz-ann-dot" style={{ background: color }} />
                        <span className="mqc-viz-ann-text" title={ann.category}>{ann.category || '—'}</span>
                        {ann.score != null && (
                          <span className="mqc-viz-ann-score">
                            {(Number(ann.score) * 100).toFixed(1)}%
                          </span>
                        )}
                        <span className="mqc-viz-ann-size">
                          {Math.round(ann.bbox[2])}×{Math.round(ann.bbox[3])}
                        </span>
                        <button
                          type="button"
                          className="mqc-vbtn is-off mqc-viz-ann-toggle"
                          title={hidden ? '显示此框' : '隐藏此框'}
                          onClick={(e) => toggleAnnHidden(idx, e)}
                        >
                          {hidden ? '○' : '●'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </aside>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
