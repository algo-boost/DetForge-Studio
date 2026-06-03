import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, toast } from '../api/client';
import StrategyEnvFields from './StrategyEnvFields';
import { fetchRecentPredictJobs, formatPredictJobLabel } from '../lib/predictJob';
import {
  buildStrategyEnvDefaults,
  buildStageEnvPayload,
  envDefaultsFromSchema,
  loadStrategyEnv,
  parseEnvRandomSeed,
  parseEnvSampleSize,
  saveStrategyEnv,
} from '../lib/envVars';

const FILTER_MODES = [
  { id: 'ng_only', label: '有框（FP）' },
  { id: 'clean_only', label: '无框（FN）' },
  { id: 'all', label: '全部' },
];

function StrategySelect({ label, value, strategies, onChange, testId }) {
  return (
    <label className="replay-label">
      {label}
      <select value={value} onChange={(e) => onChange(e.target.value)} data-testid={testId}>
        <option value="">选择策略…</option>
        {strategies.map((s) => (
          <option key={s.id} value={s.id}>{s.name || s.id}</option>
        ))}
      </select>
    </label>
  );
}

function QuickReplayPanel({ initialJobId, onCreated, onCancel }) {
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
    <>
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
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>返回</button>
        )}
      </div>
    </>
  );
}

async function resolveStrategyEnv(strategyId) {
  if (!strategyId) return {};
  const r = await api.getStrategyVariables(strategyId).catch(() => ({ data: { custom_vars: [] } }));
  const schema = r.data?.custom_vars || [];
  let meta = {};
  try {
    const s = await api.getStrategy(strategyId);
    if (s.success) meta = s.data || {};
  } catch { /* ignore */ }
  return buildStrategyEnvDefaults(schema, meta, loadStrategyEnv(strategyId));
}

export default function ReplayRunWizard({ initialJobId, onCreated, onCancel }) {
  const [mode, setMode] = useState('pipeline');
  const [strategies, setStrategies] = useState([]);
  const [models, setModels] = useState([]);
  const [stage1Id, setStage1Id] = useState('daily_trawl');
  const [stage2Id, setStage2Id] = useState('');
  const [stage1Env, setStage1Env] = useState({});
  const [stage2Env, setStage2Env] = useState({});
  const [modelId, setModelId] = useState('');
  const [threshold, setThreshold] = useState('0.1');
  const [stage1Preview, setStage1Preview] = useState(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [runBusy, setRunBusy] = useState(false);
  const [activeRun, setActiveRun] = useState(null);

  useEffect(() => {
    api.getStrategies().then((r) => {
      if (!r.success) return;
      const list = r.data || [];
      setStrategies(list);
      setStage2Id((prev) => {
        if (prev && list.some((s) => s.id === prev)) return prev;
        const hint = list.find((s) => /筛|fp/i.test(s.name || ''));
        return hint?.id || list[0]?.id || '';
      });
    }).catch(() => setStrategies([]));
    api.forgeModels(true).then((r) => {
      if (r.success) {
        const list = r.data || [];
        setModels(list);
        if (list.length && !modelId) setModelId(String(list[0].id));
      }
    }).catch(() => setModels([]));
  }, [modelId]);

  useEffect(() => {
    resolveStrategyEnv(stage1Id).then(setStage1Env).catch(() => setStage1Env({}));
  }, [stage1Id]);

  useEffect(() => {
    resolveStrategyEnv(stage2Id).then(setStage2Env).catch(() => setStage2Env({}));
  }, [stage2Id]);

  const runBody = useMemo(() => ({
    stage1: stage1Id ? { strategy_id: stage1Id } : { skip: true },
    stage2: { strategy_id: stage2Id },
    predict: {
      model_id: modelId ? Number(modelId) : undefined,
      threshold: threshold !== '' ? Number(threshold) : 0.1,
    },
    ...buildStageEnvPayload(stage1Env, stage2Env),
  }), [stage1Id, stage2Id, modelId, threshold, stage1Env, stage2Env]);

  const previewStage1 = async () => {
    if (!stage1Id) {
      toast('请选择 Stage1 策略', 'error');
      return;
    }
    setPreviewLoading(true);
    try {
      const r = await api.forgeReplayRunPreview(runBody);
      setStage1Preview(r.stages?.stage1 || null);
    } catch (e) {
      toast(e.message, 'error');
      setStage1Preview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const pollRun = useCallback(async (runId) => {
    const maxPoll = 120;
    for (let i = 0; i < maxPoll; i += 1) {
      const r = await api.forgeReplayRunGet(runId);
      const run = r.data;
      setActiveRun(run);
      if (run.status === 'done') {
        const batchId = run.curation_batch_id || run.result_json?.curation?.batch_id;
        toast(`回跑完成，批次 #${batchId || ''}`, 'success');
        onCreated?.(batchId, run);
        return;
      }
      if (run.status === 'failed') {
        toast(run.error || '回跑失败', 'error');
        return;
      }
      await new Promise((res) => { setTimeout(res, 3000); });
    }
    toast('回跑仍在进行，请稍后刷新', 'info');
  }, [onCreated]);

  const onStartRun = async () => {
    if (!stage2Id) {
      toast('请选择 Stage2 策略', 'error');
      return;
    }
    if (!modelId) {
      toast('请选择预测模型', 'error');
      return;
    }
    setRunBusy(true);
    try {
      const r = await api.forgeReplayRunCreate(runBody);
      const run = r.data;
      setActiveRun(run);
      toast(`已启动回跑 #${run.id}`, 'success');
      await pollRun(run.id);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setRunBusy(false);
    }
  };

  const stage1Name = strategies.find((s) => s.id === stage1Id)?.name;
  const stage2Name = strategies.find((s) => s.id === stage2Id)?.name;

  return (
    <section className="replay-wizard replay-run-wizard" data-testid="replay-eval-wizard">
      <div className="replay-wizard-head">
        <div>
          <h2>历史回跑</h2>
          <p className="muted">Stage1/Stage2 时段与参数在下方可调参数区配置（含开始/结束时间）；一键串行 Stage1 → 预测 → Stage2。</p>
        </div>
        {onCancel && mode !== 'quick' && (
          <button type="button" className="btn btn-sm btn-ghost" onClick={onCancel}>返回</button>
        )}
      </div>

      <div className="replay-mode-tabs">
        <button
          type="button"
          className={`replay-mode-tab${mode === 'pipeline' ? ' is-active' : ''}`}
          onClick={() => setMode('pipeline')}
          data-testid="replay-mode-pipeline"
        >
          完整流水线
        </button>
        <button
          type="button"
          className={`replay-mode-tab${mode === 'quick' ? ' is-active' : ''}`}
          onClick={() => setMode('quick')}
          data-testid="replay-mode-quick"
        >
          已有预测 · 快捷建批
        </button>
      </div>

      {mode === 'quick' ? (
        <QuickReplayPanel initialJobId={initialJobId} onCreated={onCreated} onCancel={onCancel} />
      ) : (
        <>
          <div className="replay-run-grid">
            <StrategySelect
              label="Stage1 策略"
              value={stage1Id}
              strategies={strategies}
              onChange={setStage1Id}
              testId="replay-stage1-strategy"
            />
            <StrategySelect
              label="Stage2 策略"
              value={stage2Id}
              strategies={strategies}
              onChange={setStage2Id}
              testId="replay-stage2-strategy"
            />
            <label className="replay-label">
              预测模型
              <select value={modelId} onChange={(e) => setModelId(e.target.value)} data-testid="replay-predict-model">
                <option value="">选择模型…</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>{m.name || `#${m.id}`}</option>
                ))}
              </select>
            </label>
            <label className="replay-label">
              阈值
              <input type="number" step="0.01" min="0" max="1" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            </label>
          </div>

          <div className="replay-env-stages">
            <div className="replay-env-stage" data-testid="replay-stage1-env">
              <div className="replay-env-stage-head">
                <strong>Stage1 · {stage1Name || stage1Id || '未选'}</strong>
              </div>
              <StrategyEnvFields
                strategyId={stage1Id}
                values={stage1Env}
                onChange={(env) => {
                  setStage1Env(env);
                  if (stage1Id) saveStrategyEnv(stage1Id, env);
                }}
                title="可调参数"
                compact
                testId="replay-stage1-env-fields"
              />
            </div>
            <div className="replay-env-stage" data-testid="replay-stage2-env">
              <div className="replay-env-stage-head">
                <strong>Stage2 · {stage2Name || stage2Id || '未选'}</strong>
              </div>
              <StrategyEnvFields
                strategyId={stage2Id}
                values={stage2Env}
                onChange={(env) => {
                  setStage2Env(env);
                  if (stage2Id) saveStrategyEnv(stage2Id, env);
                }}
                title="可调参数"
                compact
                testId="replay-stage2-env-fields"
              />
            </div>
          </div>

          <div className="replay-preview-inline">
            {previewLoading ? (
              <span className="muted">预览中…</span>
            ) : stage1Preview ? (
              <span data-testid="replay-stage1-preview">
                Stage1 预估 <strong>{stage1Preview.count ?? 0}</strong> 张
              </span>
            ) : (
              <button type="button" className="btn btn-sm btn-ghost" onClick={previewStage1}>预览 Stage1</button>
            )}
          </div>

          {activeRun && (
            <div className="replay-run-status muted" data-testid="replay-run-status">
              回跑 #{activeRun.id} · {activeRun.status}
              {activeRun.stage ? ` · ${activeRun.stage}` : ''}
              {activeRun.error ? ` · ${activeRun.error}` : ''}
            </div>
          )}

          <div className="replay-wizard-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={runBusy || !stage2Id || !modelId}
              onClick={onStartRun}
              data-testid="replay-start-run"
            >
              {runBusy ? '运行中…' : '一键运行回跑'}
            </button>
            {onCancel && (
              <button type="button" className="btn btn-ghost" onClick={onCancel}>返回</button>
            )}
          </div>
        </>
      )}
    </section>
  );
}
