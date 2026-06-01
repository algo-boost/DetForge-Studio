import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import { fetchRecentPredictJobs, formatPredictJobLabel } from '../lib/predictJob';

const FILTER_MODES = [
  { id: 'ng_only', label: '有框（FP）' },
  { id: 'clean_only', label: '无框（FN）' },
  { id: 'all', label: '全部' },
];

export default function ReplayEvalWizard({ initialJobId, onCreated, onCancel }) {
  const [jobs, setJobs] = useState([]);
  const [jobsLoading, setJobsLoading] = useState(true);
  const [jobId, setJobId] = useState(initialJobId ? Number(initialJobId) : null);
  const [filterMode, setFilterMode] = useState('ng_only');
  const [minScore, setMinScore] = useState('');
  const [productType, setProductType] = useState('');
  const [preview, setPreview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    fetchRecentPredictJobs(api, 30).then(setJobs).catch(() => setJobs([])).finally(() => setJobsLoading(false));
  }, []);

  useEffect(() => {
    if (initialJobId && !jobId) setJobId(Number(initialJobId));
  }, [initialJobId, jobId]);

  const previewBody = useCallback(() => ({
    job_id: jobId,
    filter_mode: filterMode,
    min_max_score: minScore !== '' ? Number(minScore) : undefined,
    product_type: productType.trim() || undefined,
  }), [jobId, filterMode, minScore, productType]);

  const loadPreview = useCallback(async () => {
    if (!jobId) return;
    setPreviewLoading(true);
    try {
      const r = await api.forgeReplayEvalPreview(previewBody());
      setPreview(r);
    } catch (e) {
      toast(e.message, 'error');
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  }, [jobId, previewBody]);

  useEffect(() => {
    if (jobId) loadPreview();
    else setPreview(null);
  }, [jobId, filterMode, minScore, productType, loadPreview]);

  const onCreate = async () => {
    if (!jobId) {
      toast('请选择预测作业', 'error');
      return;
    }
    if (!preview?.counts?.matched) {
      toast('当前筛选无样本', 'error');
      return;
    }
    setBusy(true);
    try {
      const r = await api.forgeReplayEvalCreate(previewBody());
      toast(`已创建回跑批次 ${r.batch?.batch_code || ''}`, 'success');
      onCreated?.(r.batch?.id, r);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="replay-wizard" data-testid="replay-eval-wizard">
      <div className="replay-wizard-head">
        <div>
          <h2>历史回跑</h2>
          <p className="muted">选择预测作业，按框数筛选样本并创建批次，后续走统一归档闭环</p>
        </div>
        {onCancel && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={onCancel}>返回</button>
        )}
      </div>

      <label className="replay-label">
        预测作业
        <select
          value={jobId ?? ''}
          disabled={jobsLoading}
          onChange={(e) => setJobId(e.target.value ? Number(e.target.value) : null)}
          data-testid="replay-job-select"
        >
          <option value="">{jobsLoading ? '加载中…' : '选择预测批次'}</option>
          {jobs.map((j) => (
            <option key={j.id} value={j.id}>{formatPredictJobLabel(j)}</option>
          ))}
        </select>
      </label>

      <div className="replay-mode-tabs">
        {FILTER_MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            className={`replay-mode-tab${filterMode === m.id ? ' is-active' : ''}`}
            onClick={() => setFilterMode(m.id)}
          >
            {m.label}
          </button>
        ))}
      </div>

      {jobId && (
        <div className="replay-preview-inline">
          {previewLoading ? (
            <span className="muted">统计中…</span>
          ) : preview ? (
            <span data-testid="replay-preview-matched">
              匹配 <strong>{preview.counts.matched}</strong> 张
              <span className="muted"> / 共 {preview.counts.total_all}</span>
            </span>
          ) : null}
        </div>
      )}

      <details className="replay-advanced">
        <summary>高级筛选</summary>
        <div className="replay-filters-row">
          <label>
            最低分数
            <input type="number" step="0.01" min="0" max="1" placeholder="可选" value={minScore} onChange={(e) => setMinScore(e.target.value)} />
          </label>
          <label>
            款型
            <input type="text" placeholder="可选" value={productType} onChange={(e) => setProductType(e.target.value)} />
          </label>
        </div>
      </details>

      <div className="replay-wizard-actions">
        <button
          type="button"
          className="btn btn-primary"
          disabled={busy || !jobId || !preview?.counts?.matched}
          onClick={onCreate}
          data-testid="replay-create-batch"
        >
          {busy ? '创建中…' : `创建批次（${preview?.counts?.matched ?? 0} 张）`}
        </button>
        {jobId && (
          <Link to={`/?predict_job=${jobId}`} className="btn btn-ghost">在查询页查看</Link>
        )}
      </div>
    </section>
  );
}
