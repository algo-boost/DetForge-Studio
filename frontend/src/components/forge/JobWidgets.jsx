import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, openSampleGallery, toast } from '../../api/client';
import { usePolling } from '../../hooks/usePolling';
import { showErrorModal } from '../../lib/feedbackModal';
import { formatSampleGalleryError } from '../../lib/sampleGallery';
import StatusPill from '../ui/StatusPill';
import { STATUS_MAP } from '../ui/statusMap';

/** status → 中文文案，派生自统一 STATUS_MAP，供 toast 等纯文本场景使用。 */
export const STATUS_LABEL = Object.fromEntries(
  Object.entries(STATUS_MAP).map(([k, v]) => [k, v.label]),
);

export function ProgressBar({ job }) {
  const total = Number(job.total) || 0;
  const done = Number(job.done) || 0;
  const failed = Number(job.failed) || 0;
  const finished = done + failed;
  const pct = total ? Math.round((finished / total) * 100) : 0;
  const hasFailed = failed > 0;
  const isActive = job.status === 'running' || job.status === 'pending';
  return (
    <div className="pjobs-progress">
      <div className="pjobs-progress-track">
        {done > 0 && (
          <div className="pjobs-progress-fill pjobs-progress-done" style={{ width: `${total ? (done / total) * 100 : 0}%` }} />
        )}
        {failed > 0 && (
          <div className="pjobs-progress-fill pjobs-progress-fail" style={{ width: `${total ? (failed / total) * 100 : 0}%` }} />
        )}
        {!done && !failed && pct === 0 && isActive && (
          <div className="pjobs-progress-fill pjobs-progress-active" style={{ width: '8%' }} />
        )}
      </div>
      <span className="pjobs-progress-text">
        {done}/{total}
        {hasFailed && <span className="pjobs-progress-fail-text"> · 失败 {failed}</span>}
        {' · '}{pct}%
      </span>
    </div>
  );
}

const RESULT_SORT_OPTIONS = [
  { id: 'score_desc', label: '置信度 ↓' },
  { id: 'score_asc', label: '置信度 ↑' },
  { id: 'boxes_desc', label: '框数 ↓' },
  { id: 'boxes_asc', label: '框数 ↑' },
  { id: 'id_desc', label: '最新' },
  { id: 'id_asc', label: '最早' },
];

const DEFAULT_RESULT_FILTERS = {
  q: '',
  min_box_count: '',
  min_max_score: '',
  max_max_score: '',
  categories: '',
  min_pred_confidence: '',
  max_pred_confidence: '',
  sort: 'score_desc',
  only_with_boxes: false,
  zero_boxes_only: false,
};

function exportRelPath(absPath) {
  if (!absPath) return '';
  const s = String(absPath);
  const i = s.indexOf('/exports/');
  return i >= 0 ? s.slice(i + '/exports/'.length) : s;
}

function buildResultsQuery(filters, offset, limit) {
  const p = new URLSearchParams();
  p.set('limit', String(limit));
  p.set('offset', String(offset));
  if (filters.q?.trim()) p.set('q', filters.q.trim());
  if (filters.min_box_count !== '' && filters.min_box_count != null) {
    p.set('min_box_count', String(filters.min_box_count));
  }
  if (filters.min_max_score !== '' && filters.min_max_score != null) {
    p.set('min_max_score', String(filters.min_max_score));
  }
  if (filters.max_max_score !== '' && filters.max_max_score != null) {
    p.set('max_max_score', String(filters.max_max_score));
  }
  if (filters.categories?.trim()) p.set('categories', filters.categories.trim());
  if (filters.min_pred_confidence !== '' && filters.min_pred_confidence != null) {
    p.set('min_pred_confidence', String(filters.min_pred_confidence));
  }
  if (filters.max_pred_confidence !== '' && filters.max_pred_confidence != null) {
    p.set('max_pred_confidence', String(filters.max_pred_confidence));
  }
  if (filters.only_with_boxes) p.set('only_with_boxes', '1');
  if (filters.zero_boxes_only) p.set('zero_boxes_only', '1');
  if (filters.sort) p.set('sort', filters.sort);
  return `?${p.toString()}`;
}

function filtersPayload(filters) {
  const out = { sort: filters.sort || 'score_desc' };
  if (filters.q?.trim()) out.q = filters.q.trim();
  if (filters.min_box_count !== '' && filters.min_box_count != null) {
    out.min_box_count = Number(filters.min_box_count);
  }
  if (filters.min_max_score !== '' && filters.min_max_score != null) {
    out.min_max_score = Number(filters.min_max_score);
  }
  if (filters.max_max_score !== '' && filters.max_max_score != null) {
    out.max_max_score = Number(filters.max_max_score);
  }
  if (filters.categories?.trim()) out.categories = filters.categories.trim();
  if (filters.min_pred_confidence !== '' && filters.min_pred_confidence != null) {
    out.min_pred_confidence = Number(filters.min_pred_confidence);
  }
  if (filters.max_pred_confidence !== '' && filters.max_pred_confidence != null) {
    out.max_pred_confidence = Number(filters.max_pred_confidence);
  }
  if (filters.only_with_boxes) out.only_with_boxes = true;
  if (filters.zero_boxes_only) out.zero_boxes_only = true;
  return out;
}

function DetailTab({ active, onClick, children }) {
  return (
    <button type="button" className={`pjobs-detail-tab${active ? ' is-active' : ''}`} onClick={onClick}>
      {children}
    </button>
  );
}

export function JobDetail({ job }) {
  const [failed, setFailed] = useState([]);
  const [filteredTotal, setFilteredTotal] = useState(null);
  const [logLines, setLogLines] = useState([]);
  const [tab, setTab] = useState('log');
  const [filters, setFilters] = useState({ ...DEFAULT_RESULT_FILTERS });
  const [filtersDraft, setFiltersDraft] = useState({ ...DEFAULT_RESULT_FILTERS });
  const [counting, setCounting] = useState(false);
  const [openingViz, setOpeningViz] = useState(false);
  const logWrapRef = useRef(null);
  const exportResult = job.params?.result;
  const syncResult = job.params?.result;
  const isActive = job.status === 'running' || job.status === 'pending';
  const isDone = job.status === 'done';

  const loadLogs = useCallback(async () => {
    try {
      const r = await api.forgeJobLog(job.id);
      if (r.success) setLogLines(r.lines || []);
    } catch { /* ignore */ }
  }, [job.id]);

  useEffect(() => { loadLogs(); }, [loadLogs]);
  usePolling(loadLogs, { interval: 1500, immediate: false, enabled: isActive });

  useEffect(() => {
    if (tab !== 'log' || !logWrapRef.current) return;
    const el = logWrapRef.current;
    el.scrollTop = el.scrollHeight;
  }, [logLines, tab]);

  const refreshCount = useCallback(async (activeFilters = filters) => {
    if (job.job_type !== 'predict') return;
    setCounting(true);
    try {
      const q = buildResultsQuery(activeFilters, 0, 0);
      const r = await api.forgeJobResults(job.id, q);
      if (r.success) setFilteredTotal(r.total ?? 0);
    } catch { /* ignore */ }
    finally { setCounting(false); }
  }, [job.id, job.job_type, filters]);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const f = await api.forgeJobItems(job.id, '?status=failed&limit=200');
        if (!alive) return;
        if (f.success) setFailed(f.data || []);
      } catch { /* ignore */ }
    })();
    return () => { alive = false; };
  }, [job.id]);

  useEffect(() => {
    if (job.job_type !== 'predict' || tab !== 'results') return;
    refreshCount(filters);
  }, [job.id, job.job_type, job.status, tab, filters, refreshCount]);

  const applyFilters = () => setFilters({ ...filtersDraft });
  const resetFilters = () => {
    setFiltersDraft({ ...DEFAULT_RESULT_FILTERS });
    setFilters({ ...DEFAULT_RESULT_FILTERS });
  };

  const resultCount = filteredTotal ?? (isDone ? (job.done || 0) : 0);

  const openGallery = async () => {
    if (!isDone || !resultCount) {
      showErrorModal('作业尚未完成或无符合筛选的结果', { title: '无法打开图库' });
      return;
    }
    setOpeningViz(true);
    try {
      const record = await api.forgeJobOpenViz(job.id, {
        filters: filtersPayload(filters),
        dataset_name: job.name,
      });
      openSampleGallery(record);
    } catch (e) {
      showErrorModal(formatSampleGalleryError(e, `作业 #${job.id}`), { title: '打开图库失败' });
    } finally {
      setOpeningViz(false);
    }
  };

  const resultSummary = useMemo(() => {
    if (!resultCount) return counting ? '统计中…' : '暂无结果';
    const parts = [`共 ${resultCount} 张`];
    if (filters.only_with_boxes) parts.push('仅有框');
    if (filters.zero_boxes_only) parts.push('无框');
    if (filters.min_max_score !== '') parts.push(`max≥${filters.min_max_score}`);
    if (filters.max_max_score !== '') parts.push(`max≤${filters.max_max_score}`);
    if (filters.categories?.trim()) parts.push(`类别:${filters.categories.trim()}`);
    if (filters.min_pred_confidence !== '') parts.push(`框置信≥${filters.min_pred_confidence}`);
    return parts.join(' · ');
  }, [resultCount, counting, filters]);

  return (
    <div className="pjobs-detail">
      <div className="pjobs-detail-meta">
        <StatusPill status={job.status} />
        <span className="pjobs-detail-meta-item">类型 <strong>{job.job_type}</strong></span>
        {job.total > 0 && <span className="pjobs-detail-meta-item">总量 <strong>{job.total}</strong></span>}
        {job.params?.predict_mode && (
          <span className="pjobs-detail-meta-item">模式 <strong>{job.params.predict_mode}</strong></span>
        )}
        {isDone && job.job_type === 'predict' && (
          <span className="pjobs-detail-meta-actions">
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={openingViz || !resultCount}
              onClick={openGallery}
            >
              {openingViz ? '跳转中…' : '打开样本图库'}
            </button>
            <Link className="btn btn-sm btn-ghost" to={`/?predict_job=${job.id}`}>
              查询页筛选
            </Link>
            <Link className="btn btn-sm btn-ghost" to={`/curation?replay=1&job_id=${job.id}`}>
              回跑筛选批次
            </Link>
          </span>
        )}
      </div>

      <div className="pjobs-detail-tabs">
        <DetailTab active={tab === 'log'} onClick={() => setTab('log')}>
          运行日志 {logLines.length > 0 && <span className="pjobs-detail-tab-count">{logLines.length}</span>}
          {isActive && <span className="pjobs-detail-live">实时</span>}
        </DetailTab>
        {job.job_type === 'predict' && (
          <DetailTab active={tab === 'results'} onClick={() => setTab('results')}>
            筛选 / 看图 {resultCount > 0 && <span className="pjobs-detail-tab-count">{resultCount}</span>}
          </DetailTab>
        )}
        {job.job_type === 'dataset_sync' && (
          <DetailTab active={tab === 'sync'} onClick={() => setTab('sync')}>同步结果</DetailTab>
        )}
        {job.job_type === 'manual_qc_export' && (
          <DetailTab active={tab === 'export'} onClick={() => setTab('export')}>导出结果</DetailTab>
        )}
        <DetailTab active={tab === 'failed'} onClick={() => setTab('failed')}>
          失败项 {failed.length > 0 && <span className="pjobs-detail-tab-count">{failed.length}</span>}
        </DetailTab>
        {job.error && <DetailTab active={tab === 'error'} onClick={() => setTab('error')}>作业错误</DetailTab>}
      </div>

      <div className="pjobs-detail-body">
        {tab === 'log' && (
          <div className="pjobs-log-panel">
            <p className="pjobs-log-hint muted">
              完整运行日志（<code>exports/job_logs/{job.id}.log</code>，含子进程 stderr/stdout）
              {isActive ? ' · 每 1.5s 刷新' : ''}
              {logLines.length > 0 ? ` · 共 ${logLines.length} 行` : ''}
            </p>
            {logLines.length > 0 && (
              <button
                type="button"
                className="btn btn-sm btn-ghost pjobs-log-download"
                onClick={() => {
                  const blob = new Blob([logLines.join('\n')], { type: 'text/plain;charset=utf-8' });
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(blob);
                  a.download = `job-${job.id}-log.txt`;
                  a.click();
                  URL.revokeObjectURL(a.href);
                }}
              >
                下载日志
              </button>
            )}
            <div className="pjobs-log-wrap" ref={logWrapRef}>
              {logLines.length ? (
                <pre className="pjobs-log">{logLines.join('\n')}</pre>
              ) : (
                <div className="pjobs-empty-inline">{isActive ? '等待日志输出…（大任务可能先显示「开始」再等进度）' : '暂无日志'}</div>
              )}
            </div>
          </div>
        )}
        {tab === 'export' && job.job_type === 'manual_qc_export' && (
          <div className="pjobs-result-summary">
            {exportResult ? (
              <>
                <p>已导出 <strong>{exportResult.copied}</strong> 张 / {exportResult.records} 条（缺失 {exportResult.missing}）</p>
                <p className="forge-path">目录：<code>{exportResult.out_dir}</code></p>
                {exportResult.zip_path && (
                  <a className="btn btn-sm btn-primary" href={api.forgeExportDownloadUrl(exportRelPath(exportResult.zip_path))} download>
                    下载 ZIP
                  </a>
                )}
              </>
            ) : (
              <div className="pjobs-empty-inline">{job.status === 'running' ? '导出进行中…' : '暂无导出结果'}</div>
            )}
          </div>
        )}
        {tab === 'sync' && job.job_type === 'dataset_sync' && (
          <div className="pjobs-result-summary">
            {syncResult ? (
              <>
                <p>线上 <strong>{syncResult.remote_count}</strong> 条 · COCO 图片 <strong>{syncResult.coco_images}</strong> · 标注框 <strong>{syncResult.annotations_count}</strong></p>
                <p>新下载 <strong>{syncResult.download_ok}</strong> · 跳过已有 <strong>{syncResult.skipped_existing}</strong>{syncResult.download_fail ? ` · 失败 ${syncResult.download_fail}` : ''}</p>
                <p className="forge-path">目录：<code>{syncResult.output_dir}</code></p>
              </>
            ) : (
              <div className="pjobs-empty-inline">{job.status === 'running' ? '同步进行中…' : '暂无同步结果'}</div>
            )}
          </div>
        )}
        {tab === 'results' && job.job_type === 'predict' && (
          <div className="pjobs-result-panel">
            <div className="pjobs-result-toolbar">
              <span className="pjobs-result-summary-text">{resultSummary}</span>
              <div className="pjobs-result-filters">
                <input
                  className="pjobs-filter-input"
                  placeholder="文件名…"
                  value={filtersDraft.q}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, q: e.target.value }))}
                  onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
                />
                <input
                  className="pjobs-filter-input pjobs-filter-num"
                  type="number"
                  min={0}
                  placeholder="最少框数"
                  value={filtersDraft.min_box_count}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, min_box_count: e.target.value }))}
                />
                <input
                  className="pjobs-filter-input pjobs-filter-num"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  placeholder="行 max_score ≥"
                  value={filtersDraft.min_max_score}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, min_max_score: e.target.value }))}
                />
                <input
                  className="pjobs-filter-input"
                  placeholder="缺陷类别（逗号分隔）"
                  value={filtersDraft.categories}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, categories: e.target.value }))}
                  onKeyDown={(e) => { if (e.key === 'Enter') applyFilters(); }}
                />
                <input
                  className="pjobs-filter-input pjobs-filter-num"
                  type="number"
                  min={0}
                  max={1}
                  step={0.05}
                  placeholder="框置信度 ≥"
                  title="按 ext 内各预测框的 confidence 筛选"
                  value={filtersDraft.min_pred_confidence}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, min_pred_confidence: e.target.value }))}
                />
                <select
                  className="pjobs-filter-select"
                  value={filtersDraft.sort}
                  onChange={(e) => setFiltersDraft((f) => ({ ...f, sort: e.target.value }))}
                >
                  {RESULT_SORT_OPTIONS.map((o) => (
                    <option key={o.id} value={o.id}>{o.label}</option>
                  ))}
                </select>
                <label className="pjobs-filter-check">
                  <input
                    type="checkbox"
                    checked={filtersDraft.only_with_boxes}
                    onChange={(e) => setFiltersDraft((f) => ({
                      ...f,
                      only_with_boxes: e.target.checked,
                      zero_boxes_only: e.target.checked ? false : f.zero_boxes_only,
                    }))}
                  />
                  仅有框
                </label>
                <label className="pjobs-filter-check">
                  <input
                    type="checkbox"
                    checked={filtersDraft.zero_boxes_only}
                    onChange={(e) => setFiltersDraft((f) => ({
                      ...f,
                      zero_boxes_only: e.target.checked,
                      only_with_boxes: e.target.checked ? false : f.only_with_boxes,
                    }))}
                  />
                  无框
                </label>
                <button type="button" className="btn btn-sm btn-primary" onClick={applyFilters}>筛选</button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={resetFilters}>重置</button>
              </div>
            </div>
            <div className="pjobs-result-actions">
              <p className="pjobs-result-actions-hint muted">
                筛选按 predict_result 表字段与 ext 内预测框（类别、单框置信度）；规则筛选请到查询页。
              </p>
              <div className="pjobs-result-actions-btns">
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={openingViz || !resultCount || !isDone}
                  onClick={openGallery}
                >
                  {openingViz ? '跳转中…' : '打开样本图库'}
                </button>
                <Link className="btn btn-secondary" to={`/?predict_job=${job.id}`}>
                  查询页筛选
                </Link>
              </div>
            </div>
          </div>
        )}
        {tab === 'failed' && (
          failed.length ? (
            <div className="pjobs-table-wrap">
              <table className="models-table pjobs-table">
                <thead><tr><th>项</th><th>尝试</th><th>错误</th></tr></thead>
                <tbody>
                  {failed.map((it) => (
                    <tr key={it.id}><td className="forge-path">{it.ref_key}</td><td>{it.attempts}</td><td className="forge-path">{it.error || '—'}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="pjobs-empty-inline">无失败项</div>
          )
        )}
        {tab === 'error' && <pre className="pjobs-error-box">{job.error}</pre>}
      </div>
    </div>
  );
}
