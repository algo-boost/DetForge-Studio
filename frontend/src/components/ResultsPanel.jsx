import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, toast, openSampleGalleryWhenReady } from '../api/client';
import { showErrorModal, showResultModal } from '../lib/feedbackModal';
import { buildQueryResultsReturnPath } from '../lib/viewerNav';
import { PAGE_SIZE, PREVIEW_LIMIT, LARGE_RESULT_THRESHOLD } from '../lib/constants';
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
import { formatDisplayTime } from '../lib/timezone';

const LS_AUTO_FULLSCREEN = 'pc-results-auto-fullscreen';
const LS_GRID_VIEW = 'pc-results-grid-view';
const ARCHIVE_POLL_MS = 600;
const ARCHIVE_TERMINAL = new Set(['done', 'failed']);

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
  strategyId = '', strategyName = '', viewerOpenNewWindow = false,
  pageLayout = false,
}) {
  const navigate = useNavigate();
  const [filtered, setFiltered] = useState([]);
  const [filter, setFilter] = useState({ ...DEFAULT_RESULT_FILTER });
  const [selected, setSelected] = useState(new Set());
  const [page, setPage] = useState(1);
  const [showAll, setShowAll] = useState(false);
  const [collapsed, setCollapsed] = useState(!pageLayout);
  const [fullscreen, setFullscreen] = useState(pageLayout ? false : readBool(LS_AUTO_FULLSCREEN, true));
  const [gridView, setGridView] = useState(() => readBool(LS_GRID_VIEW, true));

  useEffect(() => {
    if (!visible || !rawData.length) return;
    if (pageLayout) {
      setCollapsed(false);
      setShowAll(true);
      return;
    }
    try {
      if (new URLSearchParams(window.location.search).get('view') === 'results') {
        setCollapsed(false);
      }
    } catch { /* ignore */ }
  }, [visible, rawData.length, pageLayout]);

  useEffect(() => {
    if (!taskId || !visible) return undefined;
    const hrefs = ['/viz/', '/viz/static/vendor/plotly.min.js'];
    const links = hrefs.map((href) => {
      const link = document.createElement('link');
      link.rel = 'prefetch';
      link.as = href.endsWith('.js') ? 'script' : 'document';
      link.href = href;
      document.head.appendChild(link);
      return link;
    });
    return () => links.forEach((link) => link.remove());
  }, [taskId, visible]);

  const [activeIndex, setActiveIndex] = useState(0);
  const [viewerIdx, setViewerIdx] = useState(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [archiveDir, setArchiveDir] = useState('');
  const [archiveSub, setArchiveSub] = useState('');
  const [includeImages, setIncludeImages] = useState(true);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveJob, setArchiveJob] = useState(null);

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
      setFullscreen(pageLayout ? false : readBool(LS_AUTO_FULLSCREEN, true));
    } else {
      setShowAll(false);
      setCollapsed(true);
      setFullscreen(false);
    }
  }, [rawData, pageLayout]);

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

  const [curationBusy, setCurationBusy] = useState(false);
  const createCurationBatch = async () => {
    if (!taskId) {
      toast('无查询任务', 'error');
      return;
    }
    setCurationBusy(true);
    try {
      const r = await api.forgeCurationCreate({
        task_id: taskId,
        strategy_id: strategyId || undefined,
        strategy_name: strategyName || undefined,
        data_source: dataSource,
      });
      toast(`已创建筛选批次 ${r.data?.batch_code || ''}`, 'success');
      navigate(`/curation?id=${r.data?.id}`);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setCurationBusy(false);
    }
  };

  const openInViewer = async () => {
    if (!taskId) {
      toast('无查询任务，无法打开样本图库', 'error');
      return;
    }
    if (viewerOpening) return;
    setViewerOpening(true);
    try {
      const indices = selected.size ? [...selected] : undefined;
      await openSampleGalleryWhenReady(null, '查询结果', {
        newWindow: viewerOpenNewWindow,
        taskId,
        returnTo: buildQueryResultsReturnPath(taskId),
        openBody: {
          source: 'query_task',
          task_id: taskId,
          selected_indices: indices,
          dataset_name: executionDetail?.summary || `query-${taskId}`,
        },
      });
      toast(viewerOpenNewWindow ? '样本图库已在新窗口打开' : '正在打开样本图库…', viewerOpenNewWindow ? 'success' : 'info');
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setViewerOpening(false);
    }
  };

  const doArchive = async () => {
    if (!taskId || !archiveDir.trim() || archiveBusy) return;
    const indices = selected.size ? [...selected] : undefined;
    setArchiveBusy(true);
    setArchiveJob({ status: 'pending', progress: 0, phase_label: '提交任务', message: '正在提交…' });
    try {
      const r = await api.archive(taskId, {
        archive_dir: archiveDir.trim(),
        subfolder: archiveSub.trim(),
        selected_indices: indices,
        include_images: includeImages,
      });
      const jobId = r.archive_job_id || r.job?.id;
      if (!jobId) throw new Error('未返回归档任务 ID');
      setArchiveJob(r.job || { id: jobId, status: 'pending', progress: 0 });
      let finalJob = r.job;
      for (;;) {
        await new Promise((resolve) => setTimeout(resolve, ARCHIVE_POLL_MS));
        const st = await api.getArchiveJob(jobId);
        finalJob = st.job;
        if (!finalJob) throw new Error('归档任务不存在');
        setArchiveJob(finalJob);
        if (ARCHIVE_TERMINAL.has(finalJob.status)) break;
      }
      if (finalJob.status === 'failed') {
        throw new Error(finalJob.error || finalJob.message || '归档失败');
      }
      showResultModal(finalJob.message || `已归档到 ${finalJob.path || archiveDir}`, { title: '归档完成' });
      setArchiveOpen(false);
      onArchive?.();
    } catch (e) {
      showErrorModal(e.message || '归档失败', { title: '归档失败' });
    } finally {
      setArchiveBusy(false);
      setArchiveJob(null);
    }
  };

  if (!visible) return null;

  const summaryText = executionDetail?.summary || '';

  return (
    <>
      <div
        id="query-results-panel"
        ref={sectionRef}
        className={`results-section${pageLayout ? ' page-layout' : ''}${fullscreen ? ' fullscreen' : ''}${collapsed ? ' collapsed' : ''}${!gridView ? ' detail-view' : ''}`}
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
            {filtered.length >= LARGE_RESULT_THRESHOLD && (
              <span className="result-large-hint">共 {filtered.length} 条，建议用筛选缩小范围或使用详情视图</span>
            )}
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
              className="btn btn-sm btn-ghost"
              disabled={curationBusy || !taskId}
              onClick={createCurationBatch}
              data-testid="results-create-curation"
              title="创建筛选批次，导出 COCO 给外部筛选后回传"
            >
              {curationBusy ? '创建中…' : '归档此批'}
            </button>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              onClick={goPredict}
              title={selected.size ? `对选中的 ${selected.size} 条发起预测` : '对全部查询结果发起预测'}
              data-testid="results-predict"
            >
              预测{selected.size > 0 ? ` (${selected.size})` : ''}
            </button>
            <div className="export-dropdown">
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => setExportOpen(!exportOpen)} data-testid="results-export-toggle">导出 ▾</button>
              {exportOpen && (
                <div className="export-menu">
                  <button type="button" data-testid="results-export-coco" onClick={() => exportCoco(selected.size ? [...selected] : null)}>下载 COCO (ZIP)</button>
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
                            formatDisplayTime(item.c_time),
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

      <Modal open={archiveOpen} title="归档 COCO 到目录" onClose={() => !archiveBusy && setArchiveOpen(false)}>
        <div className="form-modal-body">
          <label className="form-label">归档目录</label>
          <input className="form-input" value={archiveDir} onChange={(e) => setArchiveDir(e.target.value)} placeholder="/path/to/archive" disabled={archiveBusy} />
          <label className="form-label">子文件夹（可选）</label>
          <input className="form-input" value={archiveSub} onChange={(e) => setArchiveSub(e.target.value)} disabled={archiveBusy} />
          <label className="rb-toggle">
            <input type="checkbox" checked={includeImages} onChange={(e) => setIncludeImages(e.target.checked)} disabled={archiveBusy} />
            {' '}
            复制图片
          </label>
          {selected.size > 0 && <p className="form-hint">将归档选中的 {selected.size} 条</p>}
          {archiveBusy && archiveJob && (
            <div className="forge-progress" style={{ marginTop: 12, flexDirection: 'column', alignItems: 'stretch', gap: 6 }}>
              <div className="forge-progress-track" style={{ width: '100%' }}>
                <div
                  className="forge-progress-fill"
                  style={{ width: `${Math.min(100, archiveJob.progress ?? 0)}%` }}
                />
              </div>
              <span className="forge-progress-text">
                {archiveJob.phase_label || archiveJob.phase || '处理中'}
                {archiveJob.total > 0 ? ` · ${archiveJob.done ?? 0}/${archiveJob.total}` : ''}
                {' · '}
                {archiveJob.progress ?? 0}%
                {archiveJob.message ? ` · ${archiveJob.message}` : ''}
              </span>
            </div>
          )}
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setArchiveOpen(false)} disabled={archiveBusy}>取消</button>
            <button type="button" className="btn btn-primary" onClick={doArchive} disabled={archiveBusy}>
              {archiveBusy ? '归档中…' : '归档'}
            </button>
          </div>
        </div>
      </Modal>
    </>
  );
}
