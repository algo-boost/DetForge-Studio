import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { buildFilterHint, getProductNo, getProductType } from '../lib/resultFilters';
import { isPredictResultRow } from '../lib/resultImage';
import { ResultImage } from './ResultImage';

function isNg(item) {
  return String(item?.check_status) === '1';
}

function statusLabel(val) {
  if (val === '1' || val === 1) return 'NG';
  if (val === '0' || val === 0) return 'OK';
  return val != null && val !== '' ? String(val) : '—';
}

function defectStats(item) {
  const map = new Map();
  (item?.annotations || []).forEach((a) => {
    const cat = a.category || '未知';
    map.set(cat, (map.get(cat) || 0) + 1);
  });
  return [...map.entries()].map(([category, count]) => ({ category, count }));
}


function DetailImageStage({ item, dataSource = 'detail' }) {
  const [dims, setDims] = useState({ w: 0, h: 0 });
  const ng = isNg(item);
  const anns = item?.annotations || [];
  const predictPreview = isPredictResultRow(item, dataSource);

  return (
    <div className="detail-stage">
      <div className="detail-stage-topbar">
        <span className={`status-badge ${ng ? 'status-ng' : 'status-ok'}`}>{ng ? 'NG' : 'OK'}</span>
        {predictPreview && item.box_count != null && (
          <span className="detail-stage-meta">预测框 {item.box_count} 个</span>
        )}
        {!predictPreview && anns.length > 0 && (
          <span className="detail-stage-meta">检测框 {anns.length} 个</span>
        )}
      </div>
      <div className="detail-stage-frame">
        <ResultImage
          item={item}
          dataSource={dataSource}
          className="detail-stage-img"
          onLoad={(e) => setDims({ w: e.target.naturalWidth, h: e.target.naturalHeight })}
        />
        {!predictPreview && dims.w > 0 && anns.length > 0 && (
          <svg
            className="detail-stage-svg"
            viewBox={`0 0 ${dims.w} ${dims.h}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {anns.map((ann, i) => {
              const [x, y, w, h] = ann.bbox || [];
              if (w == null || h == null) return null;
              const stroke = Math.max(2, dims.w / 700);
              const fontSize = Math.max(11, dims.w / 65);
              return (
                <g key={i}>
                  <rect
                    x={x}
                    y={y}
                    width={w}
                    height={h}
                    fill="none"
                    stroke="#dc2626"
                    strokeWidth={stroke}
                  />
                  <text
                    x={x}
                    y={Math.max(fontSize, y - 4)}
                    fill="#dc2626"
                    fontSize={fontSize}
                    fontFamily="system-ui, sans-serif"
                  >
                    {`${ann.category || ''} ${(ann.score ?? 0).toFixed(2)}`.trim()}
                  </text>
                </g>
              );
            })}
          </svg>
        )}
      </div>
    </div>
  );
}

function ThumbnailStrip({
  items, globalOffset, activeIndex, onSelect, dataSource = 'detail',
}) {
  const stripRef = useRef(null);

  useEffect(() => {
    const el = stripRef.current?.querySelector('.detail-thumb.is-active');
    el?.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
  }, [activeIndex]);

  const scroll = (dir) => {
    stripRef.current?.scrollBy({ left: dir * 200, behavior: 'smooth' });
  };

  return (
    <div className="detail-thumb-strip-wrap">
      <button type="button" className="detail-thumb-nav pg-btn" onClick={() => scroll(-1)} aria-label="上一组">‹</button>
      <div className="detail-thumb-strip" ref={stripRef}>
        {items.map((item, i) => {
          const globalIdx = globalOffset + i;
          const active = globalIdx === activeIndex;
          const ng = isNg(item);
          return (
            <button
              key={item.__rawIndex ?? globalIdx}
              type="button"
              className={`detail-thumb${active ? ' is-active' : ''}`}
              onClick={() => onSelect(globalIdx)}
            >
              <ResultImage item={item} dataSource={dataSource} />
              <span className={`status-badge ${ng ? 'status-ng' : 'status-ok'}`}>{ng ? 'NG' : 'OK'}</span>
            </button>
          );
        })}
      </div>
      <button type="button" className="detail-thumb-nav pg-btn" onClick={() => scroll(1)} aria-label="下一组">›</button>
    </div>
  );
}

export function InspectionResultsLayout({
  filtered,
  totalCount,
  pageData,
  globalOffset,
  activeIndex,
  onActiveIndexChange,
  selected,
  onToggleSelect,
  filter,
  dataSource = 'detail',
}) {
  const activeItem = filtered[activeIndex] ?? null;
  const stats = useMemo(() => defectStats(activeItem), [activeItem]);
  const rawIdx = activeItem?.__rawIndex ?? activeIndex;
  const isSelected = selected.has(rawIdx);
  const filterParts = useMemo(() => buildFilterHint(filter || {}), [filter]);

  const nav = useCallback((delta) => {
    const next = activeIndex + delta;
    if (next >= 0 && next < filtered.length) onActiveIndexChange(next);
  }, [activeIndex, filtered.length, onActiveIndexChange]);

  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.tagName === 'SELECT') return;
      if (e.key === 'ArrowLeft') nav(-1);
      if (e.key === 'ArrowRight') nav(1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [nav]);

  if (!activeItem) {
    return <div className="detail-empty"><p>暂无符合筛选条件的结果</p></div>;
  }

  return (
    <div className="detail-layout">
      <aside className="detail-sidebar">
        {filterParts.length > 0 && (
          <div className="detail-filter-hint">
            <strong>当前筛选</strong>
            {' · '}
            {filterParts.join(' · ')}
            {totalCount != null && (
              <>
                {' · '}
                共 {filtered.length} 条
                {filtered.length !== totalCount && ` / ${totalCount} 条`}
              </>
            )}
          </div>
        )}

        <section className="detail-panel">
          <h3 className="detail-panel-title">条目信息</h3>
          <dl className="detail-meta-list">
            <div className="detail-meta-row">
              <dt>检测时间</dt>
              <dd>{activeItem.c_time || '—'}</dd>
            </div>
            {getProductType(activeItem) && (
              <div className="detail-meta-row">
                <dt>产品型号</dt>
                <dd>{getProductType(activeItem)}</dd>
              </div>
            )}
            {getProductNo(activeItem) && (
              <div className="detail-meta-row">
                <dt>SN 码</dt>
                <dd>{getProductNo(activeItem)}</dd>
              </div>
            )}
            {activeItem.product_id && activeItem.product_id !== getProductNo(activeItem) && (
              <div className="detail-meta-row">
                <dt>产品 ID</dt>
                <dd>{activeItem.product_id}</dd>
              </div>
            )}
            {activeItem.position && (
              <div className="detail-meta-row">
                <dt>检测部位</dt>
                <dd>{activeItem.position}</dd>
              </div>
            )}
            <div className="detail-meta-row">
              <dt>文件名</dt>
              <dd className="detail-meta-mono" title={activeItem.img_name}>{activeItem.img_name}</dd>
            </div>
            <div className="detail-meta-row">
              <dt>算法</dt>
              <dd>{statusLabel(activeItem.detection_result_status)}</dd>
            </div>
            <div className="detail-meta-row">
              <dt>人工</dt>
              <dd>{statusLabel(activeItem.manual_check_status)}</dd>
            </div>
            <div className="detail-meta-row">
              <dt>状态</dt>
              <dd className={isNg(activeItem) ? 'detail-status-ng' : 'detail-status-ok'}>
                {statusLabel(activeItem.check_status)}
              </dd>
            </div>
          </dl>
        </section>

        <section className="detail-panel">
          <h3 className="detail-panel-title">缺陷统计</h3>
          {stats.length === 0 ? (
            <p className="detail-empty-hint">无检测框</p>
          ) : (
            <table className="detail-defect-table">
              <thead>
                <tr>
                  <th>类别</th>
                  <th>数量</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((row) => (
                  <tr key={row.category}>
                    <td>{row.category}</td>
                    <td>{row.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <section className="detail-panel">
          <label className="detail-select-label">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelect(rawIdx)}
            />
            选中（导出/归档）
          </label>
        </section>
      </aside>

      <main className="detail-main">
        <div className="detail-main-header">
          <h3 className="detail-main-title">预览</h3>
          <span className="detail-main-counter">{activeIndex + 1} / {filtered.length}</span>
          <div className="detail-main-nav">
            <button type="button" className="pg-btn" disabled={activeIndex <= 0} onClick={() => nav(-1)}>‹</button>
            <button type="button" className="pg-btn" disabled={activeIndex >= filtered.length - 1} onClick={() => nav(1)}>›</button>
          </div>
        </div>
        <DetailImageStage item={activeItem} dataSource={dataSource} />
        <ThumbnailStrip
          items={pageData}
          globalOffset={globalOffset}
          activeIndex={activeIndex}
          onSelect={onActiveIndexChange}
          dataSource={dataSource}
        />
      </main>
    </div>
  );
}
