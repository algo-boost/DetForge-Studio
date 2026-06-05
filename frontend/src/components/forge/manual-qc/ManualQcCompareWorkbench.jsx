import { useEffect, useMemo, useState } from 'react';
import {
  buildFilterHint,
  collectFilterOptions,
  DEFAULT_RESULT_FILTER,
  getProductNo,
  getProductType,
  isFilterActive,
} from '../../../lib/resultFilters';
import { formatDisplayTime } from '../../../lib/timezone';
import { FilterCombo, parseStatusInput, statusInputValue } from '../../FilterCombo';
import {
  isResultNg,
  resultStatusLabel,
  ThumbnailStrip,
} from '../../InspectionResultsLayout';
import DualCompareViewer from '../../viewer/DualCompareViewer';
import CandidateGridPreview from './CandidateGridPreview';
import { MATCH_LABEL, MATCH_PILL_CLASS } from './manualQcUtils';

const LS_VIEW_MODE = 'mqc-review-view-mode';

function readViewMode() {
  try {
    const v = localStorage.getItem(LS_VIEW_MODE);
    if (v === 'grid' || v === 'compare') return v;
  } catch { /* ignore */ }
  return 'compare';
}

function MatchPill({ status }) {
  const cls = MATCH_PILL_CLASS[status] || 'mqc-pill';
  return <span className={cls}>{MATCH_LABEL[status] || status || '—'}</span>;
}

function QuickFilterChip({ active, onClick, children }) {
  return (
    <button type="button" className={`mqc-filter-chip${active ? ' is-active' : ''}`} onClick={onClick}>
      {children}
    </button>
  );
}

export default function ManualQcCompareWorkbench({
  activeCase,
  customerUrl,
  rawCount,
  ngTotal,
  boxTotal,
  filteredItems,
  activeIndex,
  onActiveIndexChange,
  filter,
  onFilterChange,
  onFilterReset,
  onlyWithBoxes,
  onOnlyWithBoxesChange,
  noMatch,
  onNoMatch,
  lookupBusy,
  onRefresh,
  onVoid,
  immersive,
  onToggleImmersive,
  categories,
  defectType,
  onDefectTypeChange,
  qcCategory,
  onQcCategoryChange,
  note,
  onNoteChange,
  forceArchive,
  onForceArchiveChange,
  onSaveReview,
  onConfirm,
  busy,
  onOpenViz,
  vizOpening,
}) {
  const [viewMode, setViewMode] = useState(readViewMode);
  const [filtersOpen, setFiltersOpen] = useState(!immersive);

  useEffect(() => {
    try { localStorage.setItem(LS_VIEW_MODE, viewMode); } catch { /* ignore */ }
  }, [viewMode]);

  useEffect(() => {
    setFiltersOpen(!immersive);
  }, [immersive]);

  useEffect(() => {
    const onKey = (e) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)) return;
      if (e.key === 'g' || e.key === 'G') {
        e.preventDefault();
        if (noMatch) return;
        setViewMode((v) => (v === 'grid' ? 'compare' : 'grid'));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [noMatch]);

  const filterOptions = useMemo(() => collectFilterOptions(filteredItems), [filteredItems]);
  const activeItem = filteredItems[activeIndex] ?? null;
  const filterParts = useMemo(() => buildFilterHint(filter), [filter]);
  const ngCount = ngTotal ?? 0;
  const boxCountStat = boxTotal ?? 0;
  const filterActive = isFilterActive(filter) || onlyWithBoxes;

  const nav = (delta) => {
    const next = activeIndex + delta;
    if (next >= 0 && next < filteredItems.length) onActiveIndexChange(next);
  };

  const enterCompareAt = (idx) => {
    onActiveIndexChange(idx);
    setViewMode('compare');
  };

  return (
    <div className={`mqc-compare-workbench${immersive ? ' is-immersive' : ''}${viewMode === 'grid' ? ' is-grid-mode' : ''}`}>
      <div className="mqc-compare-toolbar">
        <div className="mqc-compare-toolbar-left">
          <span className="mqc-compare-sn">SN <strong>{activeCase.product_no}</strong></span>
          <span className="muted">案卷 #{activeCase.id}</span>
          {lookupBusy && <span className="muted">查图中…</span>}
          <span className="mqc-compare-count">
            {filteredItems.length}
            {filteredItems.length !== rawCount ? ` / ${rawCount}` : ''} 张候选
          </span>
          {viewMode === 'compare' && activeItem && !noMatch && (
            <span className="mqc-compare-count muted-inline">
              当前 #{activeItem.id}
            </span>
          )}
        </div>
        <div className="mqc-compare-toolbar-right">
          <div className="mqc-compare-view-toggle">
            <button
              type="button"
              className={`btn btn-sm btn-ghost${viewMode === 'grid' ? ' is-active' : ''}`}
              onClick={() => setViewMode('grid')}
              title="宫格浏览全部候选"
            >
              宫格
            </button>
            <button
              type="button"
              className={`btn btn-sm btn-ghost${viewMode === 'compare' ? ' is-active' : ''}`}
              onClick={() => setViewMode('compare')}
              disabled={noMatch}
              title="双栏对照看图"
            >
              对照
            </button>
          </div>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onOpenViz} disabled={vizOpening || !activeCase?.product_no}>
            {vizOpening ? '打开中…' : '样本图库'}
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onRefresh} disabled={lookupBusy}>
            刷新
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={onToggleImmersive}>
            {immersive ? '退出沉浸' : '沉浸模式'}
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => onVoid(activeCase.id)}>作废</button>
        </div>
      </div>

      <div className={`mqc-compare-filter-shell${filtersOpen ? ' is-open' : ''}`}>
        <button
          type="button"
          className="mqc-compare-filter-toggle"
          onClick={() => setFiltersOpen((v) => !v)}
          aria-expanded={filtersOpen}
        >
          {filtersOpen ? '收起筛选' : `筛选${filterActive ? ' · 已启用' : ''}`}
        </button>
        {filtersOpen && (
          <>
            <div className="mqc-compare-filter-bar result-filter-bar">
              <QuickFilterChip
                active={filter.status === 'NG' || filter.status === '1'}
                onClick={() => onFilterChange((f) => ({
                  ...f,
                  status: f.status === 'NG' || f.status === '1' ? '' : 'NG',
                }))}
              >
                仅 NG ({ngCount})
              </QuickFilterChip>
              <QuickFilterChip active={onlyWithBoxes} onClick={() => onOnlyWithBoxesChange(!onlyWithBoxes)}>
                有检测框 ({boxCountStat})
              </QuickFilterChip>
              <FilterCombo
                className="result-filter-wide"
                placeholder="产品型号"
                value={filter.productType}
                options={filterOptions.productTypes}
                onChange={(v) => onFilterChange((f) => ({ ...f, productType: v }))}
              />
              <FilterCombo
                className="result-filter-wide"
                placeholder="检测部位"
                value={filter.position}
                options={filterOptions.positions}
                onChange={(v) => onFilterChange((f) => ({ ...f, position: v }))}
              />
              <FilterCombo
                placeholder="状态"
                value={statusInputValue(filter.status)}
                options={['NG', 'OK']}
                onChange={(v) => onFilterChange((f) => ({ ...f, status: parseStatusInput(v) }))}
              />
              <FilterCombo
                placeholder="类别含…"
                value={filter.category}
                options={filterOptions.categories}
                onChange={(v) => onFilterChange((f) => ({ ...f, category: v }))}
              />
              <FilterCombo
                type="number"
                className="result-filter-score"
                placeholder="最低 score"
                value={filter.minScore}
                options={[]}
                min={0}
                max={1}
                step={0.05}
                onChange={(v) => onFilterChange((f) => ({ ...f, minScore: v }))}
              />
              <FilterCombo
                placeholder="文件名…"
                value={filter.name}
                options={filterOptions.fileNames}
                onChange={(v) => onFilterChange((f) => ({ ...f, name: v }))}
              />
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => { onFilterReset(); onOnlyWithBoxesChange(false); }}
                disabled={!filterActive}
              >
                重置
              </button>
              <button
                type="button"
                className={`btn btn-sm btn-ghost${noMatch ? ' is-active' : ''}`}
                onClick={() => onNoMatch(true)}
              >
                无匹配
              </button>
            </div>

            {(filterParts.length > 0 || onlyWithBoxes) && (
              <div className="detail-filter-hint mqc-compare-filter-hint">
                <strong>当前筛选</strong>
                {' · '}
                {[...filterParts, onlyWithBoxes ? '有检测框' : ''].filter(Boolean).join(' · ')}
                {' · '}
                共 {filteredItems.length} 条
                {filteredItems.length !== rawCount && ` / ${rawCount} 条`}
              </div>
            )}
          </>
        )}
      </div>

      <div className="mqc-compare-body">
        <main className="mqc-compare-main">
          {viewMode === 'grid' && !noMatch ? (
            <CandidateGridPreview
              items={filteredItems}
              activeIndex={activeIndex}
              onSelect={enterCompareAt}
              customerUrl={customerUrl}
            />
          ) : (
            <>
              <DualCompareViewer
                customerUrl={customerUrl}
                platformItem={noMatch ? null : activeItem}
                noMatch={noMatch}
                lookupBusy={lookupBusy}
                activeIndex={activeIndex}
                totalCount={filteredItems.length}
                onNav={nav}
              />

              {!noMatch && filteredItems.length > 0 && !immersive && (
                <ThumbnailStrip
                  items={filteredItems}
                  globalOffset={0}
                  activeIndex={activeIndex}
                  onSelect={onActiveIndexChange}
                  dataSource="detail"
                />
              )}
            </>
          )}
        </main>

        <aside className={`detail-sidebar mqc-compare-sidebar${immersive ? ' is-immersive-sidebar' : ''}`}>
          {!noMatch && activeItem && !immersive && (
            <section className="detail-panel mqc-platform-meta-panel">
              <h3 className="detail-panel-title">平台条目</h3>
              <dl className="detail-meta-list">
                <div className="detail-meta-row">
                  <dt>检测时间</dt>
                  <dd>{formatDisplayTime(activeItem.c_time)}</dd>
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
                <div className="detail-meta-row">
                  <dt>明细 ID</dt>
                  <dd className="detail-meta-mono">#{activeItem.id}</dd>
                </div>
                <div className="detail-meta-row">
                  <dt>算法</dt>
                  <dd>{resultStatusLabel(activeItem.detection_result_status)}</dd>
                </div>
                <div className="detail-meta-row">
                  <dt>状态</dt>
                  <dd className={isResultNg(activeItem) ? 'detail-status-ng' : 'detail-status-ok'}>
                    {resultStatusLabel(activeItem.check_status)}
                  </dd>
                </div>
              </dl>
            </section>
          )}

          <section className="detail-panel mqc-verdict-panel">
            <h3 className="detail-panel-title">核对定案</h3>
            <div className="forge-form-grid mqc-verdict-form-compact">
              <label>缺陷类型
                {categories.defect_strict ? (
                  <select value={defectType} onChange={(e) => onDefectTypeChange(e.target.value)}>
                    <option value="">选择…</option>
                    {categories.defect_types.map((d) => <option key={d} value={d}>{d}</option>)}
                  </select>
                ) : (
                  <input list="forge-defect-types" value={defectType} onChange={(e) => onDefectTypeChange(e.target.value)} placeholder="选择或输入" />
                )}
              </label>
              <label>成像情况 *
                <select value={qcCategory} onChange={(e) => onQcCategoryChange(e.target.value)}>
                  <option value="">选择…</option>
                  {categories.imaging_categories.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
              <label className="forge-span2">备注
                <input value={note} onChange={(e) => onNoteChange(e.target.value)} placeholder="可选" />
              </label>
              <label className="forge-inline forge-span2 mqc-checkbox-row">
                <input type="checkbox" checked={forceArchive} onChange={(e) => onForceArchiveChange(e.target.checked)} />
                强制归档
              </label>
            </div>
            <div className="mqc-verdict-footer mqc-verdict-footer-stack">
              <div className="mqc-verdict-status">
                {noMatch ? <MatchPill status="not_found" /> : activeItem
                  ? <span className="mqc-status-text">匹配 <strong>#{activeItem.id}</strong></span>
                  : <span className="mqc-status-text muted">未选匹配</span>}
              </div>
              <span className="mqc-kbd-hint">← → 切换 · G 宫格 · Ctrl+Enter 归档</span>
              <div className="mqc-verdict-actions">
                <button type="button" className="btn btn-sm btn-ghost" onClick={onSaveReview} disabled={busy}>暂存</button>
                <button type="button" className="btn btn-sm btn-primary" onClick={onConfirm} disabled={busy}>
                  {busy ? '处理中…' : '确认归档'}
                </button>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}

export { DEFAULT_RESULT_FILTER };
