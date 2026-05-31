import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, toast, openSampleGalleryWhenReady } from '../api/client';
import { PAGE_SIZE, PREVIEW_LIMIT } from '../lib/constants';
import {
  DEFAULT_RESULT_FILTER,
  collectFilterOptions,
  getProductNo,
  getProductType,
  isFilterActive,
  itemMatchesFilter,
} from '../lib/resultFilters';
import { useResultsResize } from '../hooks/useResultsResize';
import { ImageViewer } from './ImageViewer';
import { InspectionResultsLayout } from './InspectionResultsLayout';
import { FilterCombo, parseStatusInput, statusInputValue } from './FilterCombo';
import { ResultImage } from './ResultImage';
import { Modal } from './Modal';

const LS_AUTO_FULLSCREEN = 'pc-results-auto-fullscreen';
const LS_GRID_VIEW = 'pc-results-grid-view';

function readBool(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    if (v === '1') return true;
    if (v === '0') return false;
  } catch { /* ignore */ }
  return fallback;
}

function writeBool(key, val) {
  try { localStorage.setItem(key, val ? '1' : '0'); } catch { /* ignore */ }
}

export function ResultsPanel({
  visible, rawData, taskId, executionDetail, onArchive, dataSource = 'detail',
}) {
  const navigate = useNavigate();
  const [filtered, setFiltered] = useState([]);
  const [filter, setFilter] = useState({ ...DEFAULT_RESULT_FILTER });
  const [selected, setSelected] = useState(new Set());
  const [page, setPage] = useState(1);
  const [showAll, setShowAll] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [collapsed, setCollapsed] = useState(true);
  const [gridView, setGridView] = useState(() => readBool(LS_GRID_VIEW, true));
  const [activeIndex, setActiveIndex] = useState(0);
  const [viewerIdx, setViewerIdx] = useState(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveDir, setArchiveDir] = useState('');
  const [archiveSub, setArchiveSub] = useState('');
  const [includeImages, setIncludeImages] = useState(true);

  const { sectionRef, height } = useResultsResize(visible, collapsed, fullscreen);

  useEffect(() => {
    setFiltered(rawData.map((item, i) => ({ ...item, __rawIndex: i })));
    setFilter({ ...DEFAULT_RESULT_FILTER });
    setSelected(new Set());
    setPage(1);
    setActiveIndex(0);
    if (rawData.length > 0) {
      setShowAll(true);
      setCollapsed(false);
      setFullscreen(readBool(LS_AUTO_FULLSCREEN, true));
    } else {
      setShowAll(false);
      setCollapsed(true);
      setFullscreen(false);
    }
  }, [rawData]);

  useEffect(() => {
    setFiltered(isFilterActive(filter)
      ? rawData.map((item, i) => ({ ...item, __rawIndex: i })).filter((item) => itemMatchesFilter(item, filter))
      : rawData.map((item, i) => ({ ...item, __rawIndex: i })));
    setPage(1);
    setActiveIndex(0);
  }, [filter, rawData]);

  const filterOptions = useMemo(() => collectFilterOptions(rawData), [rawData]);

  const inPreview = !showAll && !fullscreen && filtered.length > PREVIEW_LIMIT;
  const pageData = useMemo(() => {
    if (inPreview) return filtered.slice(0, PREVIEW_LIMIT);
    const start = (page - 1) * PAGE_SIZE;
    return filtered.slice(start, start + PAGE_SIZE);
  }, [filtered, page, inPreview]);

  const totalPages = Math.ceil(filtered.length / PAGE_SIZE);

  const navItems = inPreview ? filtered.slice(0, PREVIEW_LIMIT) : filtered;
  const navGlobalOffset = inPreview ? 0 : (page - 1) * PAGE_SIZE;
  const thumbPageData = inPreview
    ? navItems
    : filtered.slice(navGlobalOffset, navGlobalOffset + PAGE_SIZE);

  useEffect(() => {
    if (!navItems.length) return;
    if (activeIndex >= navItems.length) setActiveIndex(0);
    else if (!inPreview && filtered.length) {
      const expectedPage = Math.floor(activeIndex / PAGE_SIZE) + 1;
      if (expectedPage !== page) setPage(expectedPage);
    }
  }, [activeIndex, navItems.length, inPreview, filtered.length, page]);

  const toggleSelect = (rawIdx) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(rawIdx)) n.delete(rawIdx); else n.add(rawIdx);
      return n;
    });
  };

  const toggleSelectAll = (checked) => {
    if (checked) setSelected(new Set(filtered.map((x) => x.__rawIndex)));
    else setSelected(new Set());
  };

  const exportCoco = (indices) => {
    if (!taskId) return;
    if (indices?.length) {
      fetch(`/api/export/${taskId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ selected_indices: indices }),
      }).then((r) => r.blob()).then((blob) => {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `coco_${taskId}.zip`;
        a.click();
      });
    } else {
      window.open(api.exportCocoUrl(taskId), '_blank');
    }
    setExportOpen(false);
  };

  const [viewerOpening, setViewerOpening] = useState(false);

  const goPredict = () => {
    if (!taskId) {
      toast('无查询任务，无法发起预测', 'error');
      return;
    }
    const params = new URLSearchParams({ task: taskId });
    if (selected.size > 0) {
      params.set('indices', [...selected].sort((a, b) => a - b).join(','));
    }
    navigate(`/online-predict?${params.toString()}`);
  };

  const openInViewer = async () => {
    if (!taskId) {
      toast('无查询任务，无法打开样本图库', 'error');
      return;
    }
    if (viewerOpening) return;
    setViewerOpening(true);
    toast('正在准备样本图库…', 'info');
    try {
      const indices = selected.size ? [...selected] : undefined;
      await openSampleGalleryWhenReady(() => api.vizOpen({
        source: 'query_task',
        task_id: taskId,
        selected_indices: indices,
        dataset_name: executionDetail?.summary || `query-${taskId}`,
      }));
      toast('样本图库已在新窗口打开', 'success');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setViewerOpening(false);
    }
  };

  const doArchive = async () => {
    if (!taskId || !archiveDir.trim()) return;
    const indices = selected.size ? [...selected] : undefined;
    await api.archive(taskId, {
      archive_dir: archiveDir.trim(),
      subfolder: archiveSub.trim(),
      selected_indices: indices,
      include_images: includeImages,
    });
    setArchiveOpen(false);
    onArchive?.();
  };

  if (!visible) return null;

  const summaryText = executionDetail?.summary || '';

  return (
    <>
      <div
        ref={sectionRef}
        className={`results-section${fullscreen ? ' fullscreen' : ''}${collapsed ? ' collapsed' : ''}${!gridView ? ' detail-view' : ''}`}
        style={{ display: 'flex', ...(collapsed || fullscreen ? {} : { '--results-h': `${height}px`, height: `${height}px` }) }}
      >
        {!collapsed && !fullscreen && (
          <div className="results-resize-handle" title="拖拽调整结果区高度">
            <span className="resize-grip" />
          </div>
        )}
        <div className="toolbar">
          <div className="toolbar-left">
            <span
              className="result-count result-count-clickable"
              onClick={() => collapsed && setCollapsed(false)}
              title="点击展开结果"
            >
              {filtered.length}{filtered.length !== rawData.length ? ` / ${rawData.length}` : ''} 条结果
            </span>
            <div className="result-filter-bar">
              <input
                type="datetime-local"
                className="result-filter-combo result-filter-time"
                title="检测时间起"
                value={filter.timeStart}
                onChange={(e) => setFilter((f) => ({ ...f, timeStart: e.target.value }))}
              />
              <span className="result-filter-sep">~</span>
              <input
                type="datetime-local"
                className="result-filter-combo result-filter-time"
                title="检测时间止"
                value={filter.timeEnd}
                onChange={(e) => setFilter((f) => ({ ...f, timeEnd: e.target.value }))}
              />
              <FilterCombo
                className="result-filter-wide"
                placeholder="产品型号"
                value={filter.productType}
                options={filterOptions.productTypes}
                onChange={(v) => setFilter((f) => ({ ...f, productType: v }))}
              />
              <FilterCombo
                className="result-filter-sn"
                placeholder="SN 码"
                value={filter.productNo}
                options={filterOptions.productNos}
                onChange={(v) => setFilter((f) => ({ ...f, productNo: v }))}
              />
              <FilterCombo
                className="result-filter-id"
                placeholder="产品 ID"
                value={filter.productId}
                options={filterOptions.productIds}
                onChange={(v) => setFilter((f) => ({ ...f, productId: v }))}
              />
              <FilterCombo
                className="result-filter-wide"
                placeholder="检测部位"
                value={filter.position}
                options={filterOptions.positions}
                onChange={(v) => setFilter((f) => ({ ...f, position: v }))}
              />
              <FilterCombo
                placeholder="状态"
                value={statusInputValue(filter.status)}
                options={['NG', 'OK']}
                onChange={(v) => setFilter((f) => ({ ...f, status: parseStatusInput(v) }))}
              />
              <FilterCombo
                placeholder="类别含…"
                value={filter.category}
                options={filterOptions.categories}
                onChange={(v) => setFilter((f) => ({ ...f, category: v }))}
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
                onChange={(v) => setFilter((f) => ({ ...f, minScore: v }))}
              />
              <FilterCombo
                placeholder="文件名…"
                value={filter.name}
                options={filterOptions.fileNames}
                onChange={(v) => setFilter((f) => ({ ...f, name: v }))}
              />
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setFilter({ ...DEFAULT_RESULT_FILTER })}>重置</button>
            </div>
            {summaryText && (
              <span className="result-summary is-clickable" onClick={() => setDetailOpen(true)} title="点击查看完整执行详情">{summaryText}</span>
            )}
            {inPreview && <span className="result-preview-hint">预览 {PREVIEW_LIMIT} 张</span>}
            {selected.size > 0 && <span className="result-selected">已选 <strong>{selected.size}</strong></span>}
          </div>
          <div className="toolbar-right">
            {filtered.length > PREVIEW_LIMIT && (
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setShowAll(!showAll); setCollapsed(false); }}>
                {showAll ? '仅预览 5 张' : `查看全部 ${filtered.length} 条`}
              </button>
            )}
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setCollapsed(!collapsed)}>{collapsed ? '展开' : '收起'}</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => { const next = !fullscreen; setFullscreen(next); if (next) setShowAll(true); writeBool(LS_AUTO_FULLSCREEN, next); }}>{fullscreen ? '退出全屏' : '全屏'}</button>
            <label className="cb-label"><input type="checkbox" checked={selected.size === filtered.length && filtered.length > 0} onChange={(e) => toggleSelectAll(e.target.checked)} /> 全选</label>
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => { const next = !gridView; setGridView(next); writeBool(LS_GRID_VIEW, next); }} title={gridView ? '详情视图' : '网格视图'}>{gridView ? '▦' : '☰'}</button>
            <button type="button" className="btn btn-sm btn-primary" disabled={viewerOpening} onClick={openInViewer} title="在新窗口打开样本图库，浏览、筛选与标注">{viewerOpening ? '打开中…' : '打开样本图库'}</button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={goPredict}
              title={selected.size ? `对选中的 ${selected.size} 条发起预测` : '对全部查询结果发起预测'}
            >
              预测{selected.size > 0 ? ` (${selected.size})` : ''}
            </button>
            <div className="export-dropdown">
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setExportOpen(!exportOpen)}>导出 ▾</button>
              {exportOpen && (
                <div className="export-menu">
                  <button type="button" onClick={() => exportCoco(selected.size ? [...selected] : null)}>下载 COCO (ZIP)</button>
                  <button type="button" onClick={() => { window.open(api.exportCsvUrl(taskId), '_blank'); setExportOpen(false); }}>下载 CSV</button>
                  <div className="export-menu-divider" />
                  <button type="button" onClick={() => { setArchiveOpen(true); setExportOpen(false); }}>归档 COCO 到目录…</button>
                </div>
              )}
            </div>
          </div>
        </div>
        {!collapsed && (
          <div className="results-body">
            <div className="results-area">
              {filtered.length === 0 ? (
                <div className="empty-result"><p>暂无结果</p></div>
              ) : gridView ? (
                <div className="image-grid">
                  {pageData.map((item, i) => (
                    <div key={item.__rawIndex} className={`img-card${selected.has(item.__rawIndex) ? ' selected' : ''}`} onClick={() => setViewerIdx(inPreview ? i : (page - 1) * PAGE_SIZE + i)}>
                      {dataSource === 'predict_result' && (item.box_count ?? 0) > 0 && (
                        <span className="status-badge status-ng">NG</span>
                      )}
                      {dataSource === 'predict_result' && (item.box_count ?? 0) === 0 && (
                        <span className="status-badge status-ok">OK</span>
                      )}
                      {dataSource !== 'predict_result' && item.check_status === '1' && (
                        <span className="status-badge status-ng">NG</span>
                      )}
                      {dataSource !== 'predict_result' && item.check_status === '0' && (
                        <span className="status-badge status-ok">OK</span>
                      )}
                      <div className="select-check" onClick={(e) => { e.stopPropagation(); toggleSelect(item.__rawIndex); }}>✓</div>
                      <div className="img-wrap"><ResultImage item={item} dataSource={dataSource} /></div>
                      <div className="img-bottom">
                        <div className="img-name">{item.img_name}</div>
                        <div className="img-meta">
                          {[
                            dataSource === 'predict_result' && item.box_count != null && `${item.box_count} 框`,
                            dataSource === 'predict_result' && item.max_score != null && `max ${Number(item.max_score).toFixed(2)}`,
                            getProductType(item) && `型号 ${getProductType(item)}`,
                            getProductNo(item) && `SN ${getProductNo(item)}`,
                            item.product_id && `ID ${item.product_id}`,
                            item.c_time,
                          ].filter(Boolean).join(' · ')}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <InspectionResultsLayout
                  filtered={navItems}
                  totalCount={rawData.length}
                  pageData={thumbPageData}
                  globalOffset={navGlobalOffset}
                  activeIndex={Math.min(activeIndex, Math.max(navItems.length - 1, 0))}
                  onActiveIndexChange={setActiveIndex}
                  selected={selected}
                  onToggleSelect={toggleSelect}
                  filter={filter}
                  dataSource={dataSource}
                />
              )}
              {gridView && !inPreview && totalPages > 1 && (
                <div className="paginator">
                  <button type="button" className="pg-btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹</button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).slice(0, 7).map((p) => (
                    <button key={p} type="button" className={`pg-btn${p === page ? ' active' : ''}`} onClick={() => setPage(p)}>{p}</button>
                  ))}
                  <button type="button" className="pg-btn" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>›</button>
                </div>
              )}
              {!gridView && !inPreview && totalPages > 1 && (
                <div className="paginator">
                  <button type="button" className="pg-btn" disabled={page <= 1} onClick={() => { setPage(page - 1); setActiveIndex((page - 2) * PAGE_SIZE); }}>‹</button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1).slice(0, 7).map((p) => (
                    <button key={p} type="button" className={`pg-btn${p === page ? ' active' : ''}`} onClick={() => { setPage(p); setActiveIndex((p - 1) * PAGE_SIZE); }}>{p}</button>
                  ))}
                  <button type="button" className="pg-btn" disabled={page >= totalPages} onClick={() => { setPage(page + 1); setActiveIndex(page * PAGE_SIZE); }}>›</button>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {viewerIdx != null && (
        <ImageViewer
          items={filtered}
          index={viewerIdx}
          selected={selected}
          onClose={() => setViewerIdx(null)}
          onNav={setViewerIdx}
          onToggleSelect={toggleSelect}
          dataSource={dataSource}
        />
      )}

      <Modal open={detailOpen} title="执行详情" wide onClose={() => setDetailOpen(false)}>
        <pre className="console-pre" style={{ padding: 16, maxHeight: 400, overflow: 'auto' }}>{executionDetail?.detail || summaryText}</pre>
      </Modal>

      <Modal open={archiveOpen} title="归档 COCO 到目录" onClose={() => setArchiveOpen(false)}>
        <div className="form-modal-body">
          <label className="form-label">归档目录</label>
          <input className="form-input" value={archiveDir} onChange={(e) => setArchiveDir(e.target.value)} placeholder="/path/to/archive" />
          <label className="form-label">子文件夹（可选）</label>
          <input className="form-input" value={archiveSub} onChange={(e) => setArchiveSub(e.target.value)} />
          <label className="rb-toggle"><input type="checkbox" checked={includeImages} onChange={(e) => setIncludeImages(e.target.checked)} /> 复制图片</label>
          {selected.size > 0 && <p className="form-hint">将归档选中的 {selected.size} 条</p>}
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setArchiveOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={doArchive}>归档</button>
          </div>
        </div>
      </Modal>
    </>
  );
}
