import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom';
import { api, formatSqlTime, toast, openSampleGalleryWhenReady } from '../api/client';
import { useQueryJobs } from '../context/QueryJobsContext';
import { SqlEditor, PythonEditor } from '../components/Editors';
import { PythonCodeWorkspace } from '../components/PythonCodeWorkspace';
import { RulesBuilder } from '../components/RulesBuilder';
import { StrategyPicker } from '../components/StrategyPicker';
import SceneHubNav from '../components/SceneHubNav';
import { PYTHON_HELP, ConsolePanel } from '../components/ConsolePanel';
import { formatConsoleSummary } from '../lib/consoleOutput';
import { Modal } from '../components/Modal';
import { useRulesStudio } from '../hooks/useRulesStudio';
import { useEditorWorkspace, FullscreenIcon } from '../hooks/useEditorWorkspace';
import { DEFAULT_PY, DEFAULT_SAMPLE, DEFAULT_SEED, DEFAULT_SQL, DEFAULT_DETAIL_SQL, DEFAULT_PREDICT_SQL, buildPredictJobSql } from '../lib/constants';
import { fetchRecentPredictJobs, formatPredictJobLabel, parsePredictJobIdFromSql, resolvePredictJobId } from '../lib/predictJob';
import { buildHistoryEntry, saveHistoryEntry } from '../lib/history';
import { setTimePreset } from '../lib/time';
import { backendFilterMode, hasComplexFlow, mergeFlowForSave, pythonNeedsFilterRules, uiFilterMode } from '../lib/flowMerge';
import StrategyEnvFields from '../components/StrategyEnvFields';
import {
  buildStrategyEnvDefaults,
  extractSqlTemplateVars,
  formatEnvDateTime,
  loadStrategyEnv,
  parseEnvRandomSeed,
  parseEnvSampleSizeOptional,
  saveStrategyEnv,
  toDatetimeLocalValue,
  RUNTIME_VAR_LABELS,
} from '../lib/envVars';
import { TIME_ENV_FIELDS } from '../lib/strategyEnvSchema';
import { inferDataSourceFromStrategy, parseDefaultPredictJobId } from '../lib/strategyDataSource';
import { shouldUseFullProcessPreview } from '../lib/previewMode';
import { buildQueryResultsReturnPath } from '../lib/viewerNav';
import { buildQueryResultsPath, saveLastQueryTaskId } from '../lib/queryResultsNav';
import { showErrorModal, showInfoModal, showResultModal } from '../lib/feedbackModal';
import {
  QUERY_UI_MODE_COMPACT,
  QUERY_UI_MODE_FULL,
  QUERY_UI_MODE_OPTIONS,
  loadQueryUiModePreference,
  queryUiModeLabel,
  resolveQueryUiMode,
  saveQueryUiModePreference,
} from '../lib/queryUiMode';
import {
  defaultCompactHideMap,
  serializeCompactHideForSave,
  resolveCompactHideMap,
  shouldHideInCompact,
  showCompactFilterRules,
} from '../lib/queryCompactHide';
import {
  extractSampleFromSampleCode,
  hasInlineSampling,
  hasInlineSamplingInFlow,
  normalizeProcessSampleCall,
  patchFlowSample,
  resolveSampleSettings,
  resolveSampleCodeForExecution,
  splitStrategyPython,
} from '../lib/sampleSync';

function prepareImportedStrategy(raw) {
  const data = { ...raw };
  if (data._builtin) delete data._builtin;
  return data;
}

function resolveInitialQueryState() {
  const savedDs = localStorage.getItem('pc_data_source');
  const savedSql = localStorage.getItem('pc_sql');
  if (savedDs === 'detail') {
    return { dataSource: 'detail', sql: savedSql || DEFAULT_DETAIL_SQL };
  }
  if (savedDs === 'predict_result') {
    return { dataSource: 'predict_result', sql: savedSql || DEFAULT_PREDICT_SQL };
  }
  if (savedSql && !savedSql.includes('product_detection_detail_result')) {
    return { dataSource: 'predict_result', sql: savedSql };
  }
  return { dataSource: 'predict_result', sql: DEFAULT_PREDICT_SQL };
}

function sqlNeedsTimeRange(currentSql, source, jobId) {
  if (source === 'predict_result') {
    if (jobId || !currentSql.includes('${START_TIME}')) return false;
  }
  return currentSql.includes('${START_TIME}') || currentSql.includes('${END_TIME}');
}

function envTimeReady(env) {
  return Boolean(String(env?.START_TIME || '').trim() && String(env?.END_TIME || '').trim());
}

export default function QueryPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const restored = useRef(false);
  const initialQuery = resolveInitialQueryState();
  const [sql, setSql] = useState(initialQuery.sql);
  const [pythonCode, setPythonCode] = useState(() => localStorage.getItem('pc_python') || DEFAULT_PY);
  const [sampleCode, setSampleCode] = useState('');
  const [filterMode, setFilterMode] = useState('rules');
  const [strategies, setStrategies] = useState([]);
  const [dataSource, setDataSource] = useState(initialQuery.dataSource);
  const [predictJobId, setPredictJobId] = useState(null);
  const [predictJobs, setPredictJobs] = useState([]);
  const [predictJobsLoading, setPredictJobsLoading] = useState(false);
  const [pendingAutoExecJobId, setPendingAutoExecJobId] = useState(null);
  const [loadedPresetId, setLoadedPresetId] = useState('');
  const [queryUiMode, setQueryUiMode] = useState(() => loadQueryUiModePreference());
  const [compactHide, setCompactHide] = useState(() => defaultCompactHideMap());
  const originalFlowRef = useRef(null);
  const savedFilterRulesCodeRef = useRef('');
  const [submitting, setSubmitting] = useState(false);
  const { submitQueryJob, runningCount } = useQueryJobs();
  const [previewStats, setPreviewStats] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewStale, setPreviewStale] = useState(true);
  const [imgPathHint, setImgPathHint] = useState('');
  const [console, setConsole] = useState(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const [deleteId, setDeleteId] = useState('');
  const [queryEnv, setQueryEnv] = useState({});
  const [envSchema, setEnvSchema] = useState([]);
  const [processPipeline, setProcessPipeline] = useState([]);
  const [viewerOpenNewWindow, setViewerOpenNewWindow] = useState(false);
  const viewerOpenNewWindowRef = useRef(false);
  const importRef = useRef(null);
  const pythonFileRef = useRef(null);
  const skipSampleSyncRef = useRef(false);
  const prevSampleRef = useRef({ sampleSize: DEFAULT_SAMPLE, randomSeed: DEFAULT_SEED });
  const pythonCodeRef = useRef(pythonCode);
  const sampleCodeRef = useRef(sampleCode);
  pythonCodeRef.current = pythonCode;
  sampleCodeRef.current = sampleCode;

  const markStale = useCallback(() => setPreviewStale(true), []);
  const setQueryUiModePersist = useCallback((mode) => {
    setQueryUiMode(mode);
    saveQueryUiModePreference(mode);
  }, []);
  const studio = useRulesStudio(markStale);
  const editorWs = useEditorWorkspace();

  const sampleSize = useMemo(() => parseEnvSampleSizeOptional(queryEnv), [queryEnv]);
  const randomSeed = useMemo(() => parseEnvRandomSeed(queryEnv, DEFAULT_SEED), [queryEnv]);
  const needsTimeRange = useMemo(
    () => sqlNeedsTimeRange(sql, dataSource, predictJobId),
    [sql, dataSource, predictJobId],
  );
  /** 时段与其它参数统一在「策略参数」区，不再单独显示顶部日期条 */
  const displayEnvSchema = useMemo(() => {
    if (envSchema.length) return envSchema;
    if (needsTimeRange && dataSource !== 'predict_result') return TIME_ENV_FIELDS;
    return [];
  }, [envSchema, needsTimeRange, dataSource]);
  const showStrategyEnv = displayEnvSchema.length > 0 || Boolean(loadedPresetId);

  const patchQueryEnv = useCallback((patch, { save = true } = {}) => {
    setQueryEnv((prev) => {
      const next = { ...prev, ...patch };
      if (save && loadedPresetId) saveStrategyEnv(loadedPresetId, next);
      return next;
    });
    markStale();
  }, [loadedPresetId, markStale]);

  const patchQueryEnvSample = useCallback(({ sampleSize: ss, randomSeed: rs }) => {
    const patch = {};
    if (ss != null) patch.SAMPLE_SIZE = String(ss);
    if (rs != null) patch.RANDOM_SEED = String(rs);
    if (Object.keys(patch).length) patchQueryEnv(patch);
  }, [patchQueryEnv]);

  const resolveFilterRulesCode = useCallback(async () => {
    if (studio.rules.length) {
      const compiled = await studio.compile();
      if (compiled?.trim()) return compiled;
      if (studio.flow?.nodes?.length) {
        try {
          const res = await api.compileFlow({ flow: studio.flow, target: 'filter_rules' });
          if (res.success && res.python_code?.trim()) return res.python_code.trim();
        } catch { /* ignore */ }
      }
    }
    return savedFilterRulesCodeRef.current?.trim() || '';
  }, [studio]);

  const ensureFilterRulesReady = useCallback(async () => {
    if (!pythonNeedsFilterRules(pythonCode)) return true;
    const rulesCode = await resolveFilterRulesCode();
    if (rulesCode.trim()) return true;
    showErrorModal('代码调用了 apply_filter_rules()，但未找到规则。请在「规则」页添加筛选条件，或加载含规则的策略。', { title: '无法执行' });
    return false;
  }, [pythonCode, resolveFilterRulesCode]);

  const reloadStrategies = useCallback(async () => {
    const r = await api.getStrategies();
    if (r.success) setStrategies(r.data || []);
  }, []);

  const applySnapshot = useCallback((snap) => {
    if (!snap) return;
    if (snap.sql_template) setSql(snap.sql_template);
    const split = splitStrategyPython({
      pythonCode: snap.python_code,
      sampleCode: snap.sample_code,
    });
    if (snap.python_code) setPythonCode(normalizeProcessSampleCall(split.processCode));
    if (snap.sample_code != null) setSampleCode(snap.sample_code || split.sampleCode || '');
    const m = snap.filter_mode;
    if (m) setFilterMode(uiFilterMode(m));
    if (snap.flow) {
      studio.setFlow(snap.flow, { removeEmptyRows: snap.remove_empty_rows });
    }
    savedFilterRulesCodeRef.current = snap.filter_rules_code || '';
    const sample = resolveSampleSettings({
      pythonCode: split.processCode,
      sampleCode: snap.sample_code || split.sampleCode,
      flow: snap.flow,
      sampleSize: snap.sample_size,
      randomSeed: snap.random_seed,
    });
    skipSampleSyncRef.current = true;
    prevSampleRef.current = { sampleSize: sample.sampleSize, randomSeed: sample.randomSeed };
    patchQueryEnvSample({ sampleSize: sample.sampleSize, randomSeed: sample.randomSeed });
    queueMicrotask(() => { skipSampleSyncRef.current = false; });
    markStale();
  }, [studio, markStale, patchQueryEnvSample]);

  const refreshPathChecks = useCallback(async (trySync = false) => {
    let res = await api.getConfig();
    if (!res.success) return;
    const mode = res.config?.img_path_mode || 'concat';
    if (trySync && res.path_checks?.img_base_path_exists === false && mode === 'concat') {
      const sync = await api.syncPlatformPaths({});
      if (sync.success && sync.changed) {
        res = await api.getConfig();
      } else if (sync.success && sync.local_file_base && !sync.changed) {
        setImgPathHint('图片根目录不可用，查询仍可进行；预览图可能无法加载');
      }
    }
    if (res.success) {
      if (res.path_checks?.img_base_path_exists === false) {
        const p = res.config?.img_base_path || res.config?.local_file_base;
        setImgPathHint(p
          ? `图片根目录不存在（${p}），查询可正常执行，缩略图需挂载盘符或到设置页修正路径`
          : '图片根目录未配置，查询可正常执行');
      } else {
        setImgPathHint('');
      }
    }
  }, []);

  useEffect(() => {
    const p = setTimePreset('7days');
    setQueryEnv({
      START_TIME: formatEnvDateTime(p.start),
      END_TIME: formatEnvDateTime(p.end),
    });
    refreshPathChecks(true);
    reloadStrategies().then(() => {
      const urlStrategy = searchParams.get('strategy');
      const urlDs = searchParams.get('data_source');
      if (urlDs === 'detail' || urlDs === 'predict_result') {
        setDataSource(urlDs);
      }
      if (urlStrategy) {
        loadStrategy(urlStrategy);
        return;
      }
      const last = localStorage.getItem('pc_last_preset');
      if (last && last !== '__free__') loadStrategy(last);
      else loadStrategy('daily_trawl');
    });
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const urlTaskId = searchParams.get('task') || '';
  const urlViewResults = searchParams.get('view') === 'results';

  useEffect(() => {
    if (urlViewResults && urlTaskId) {
      navigate(buildQueryResultsPath(urlTaskId), { replace: true });
    }
  }, [urlViewResults, urlTaskId, navigate]);

  useEffect(() => {
    api.getConfig().then((r) => {
      const on = !!r.config?.viz_open_new_window;
      setViewerOpenNewWindow(on);
      viewerOpenNewWindowRef.current = on;
    }).catch(() => {});
  }, []);

  useEffect(() => {
    viewerOpenNewWindowRef.current = viewerOpenNewWindow;
  }, [viewerOpenNewWindow]);

  useEffect(() => {
    if (restored.current || !location.state?.restore) return;
    restored.current = true;
    const item = location.state.restore;
    if (item.start_raw || item.end_raw) {
      patchQueryEnv({
        ...(item.start_raw ? { START_TIME: formatEnvDateTime(item.start_raw) } : {}),
        ...(item.end_raw ? { END_TIME: formatEnvDateTime(item.end_raw) } : {}),
      }, { save: false });
    }
    if (item.snapshot) applySnapshot(item.snapshot);
    else if (item.strategy_id) loadStrategy(item.strategy_id);
    if (item.sample_size != null || item.random_seed != null) {
      patchQueryEnv({
        ...(item.sample_size != null ? { SAMPLE_SIZE: String(item.sample_size) } : {}),
        ...(item.random_seed != null ? { RANDOM_SEED: String(item.random_seed) } : {}),
      }, { save: false });
    }
    if (location.state.autoExecute) setTimeout(() => onExecuteRef.current?.(), 300);
    toast(`已恢复：${item.strategy}`);
  }, [location.state]);

  useEffect(() => {
    const onOpenSave = (e) => {
      setSaveName(e.detail?.name || strategies.find((s) => s.id === loadedPresetId)?.name || '');
      setSaveOpen(true);
    };
    window.addEventListener('pc-open-save-strategy', onOpenSave);
    return () => window.removeEventListener('pc-open-save-strategy', onOpenSave);
  }, [strategies, loadedPresetId]);

  useEffect(() => { localStorage.setItem('pc_sql', sql); markStale(); }, [sql, markStale]);
  useEffect(() => { localStorage.setItem('pc_data_source', dataSource); }, [dataSource]);
  useEffect(() => {
    if (predictJobId) localStorage.setItem('pc_predict_job_id', String(predictJobId));
    else localStorage.removeItem('pc_predict_job_id');
  }, [predictJobId]);

  const applyPredictBatchSql = useCallback(async (jobId, { silent = false, table } = {}) => {
    let tableName = table;
    if (!tableName) {
      const res = await api.forgePredictResultSource();
      if (!res.success) throw new Error(res.error || '无法加载预测结果表');
      tableName = res.table;
    }
    setDataSource('predict_result');
    if (jobId) {
      setPredictJobId(Number(jobId));
      setSql(buildPredictJobSql(tableName, jobId));
      if (!silent) toast(`已匹配预测批次 #${jobId}`);
    } else {
      setSql(buildPredictJobSql(tableName, null));
    }
    markStale();
  }, [markStale]);

  const ensurePredictBatchReady = useCallback(async ({ silent = true } = {}) => {
    if (dataSource !== 'predict_result') return null;
    const recent = predictJobs.length ? predictJobs : await fetchRecentPredictJobs(api);
    if (!predictJobs.length && recent.length) setPredictJobs(recent);
    const jobId = await resolvePredictJobId({
      urlJobId: searchParams.get('predict_job'),
      sql,
      recentJobs: recent,
    });
    if (!jobId) throw new Error('没有可用的预测作业，请先完成一次预测');
    const src = await api.forgePredictResultSource();
    if (!src.success) throw new Error(src.error || '无法加载预测结果表');
    const nextSql = buildPredictJobSql(src.table, jobId);
    const parsed = parsePredictJobIdFromSql(sql);
    if (parsed !== jobId || !sql.includes('predict_result') || sql !== nextSql) {
      setDataSource('predict_result');
      setPredictJobId(jobId);
      setSql(nextSql);
      if (!silent) toast(`已匹配预测批次 #${jobId}`);
      markStale();
    } else if (predictJobId !== jobId) {
      setPredictJobId(jobId);
    }
    return { jobId, sql: nextSql, table: src.table };
  }, [dataSource, predictJobs, searchParams, sql, predictJobId, markStale]);

  useEffect(() => {
    if (sql.includes('predict_result') && dataSource !== 'predict_result') {
      setDataSource('predict_result');
    }
    if (dataSource !== 'predict_result') return;
    const parsed = parsePredictJobIdFromSql(sql);
    if (parsed && parsed !== predictJobId) setPredictJobId(parsed);
  }, [sql, dataSource, predictJobId]);
  useEffect(() => { localStorage.setItem('pc_python', pythonCode); markStale(); }, [pythonCode, markStale]);

  const uiBackendMode = backendFilterMode(filterMode);
  const flowPayload = filterMode === 'code' ? null : studio.flow;
  const resolvedFlow = mergeFlowForSave(originalFlowRef.current, flowPayload, studio.removeEmpty);
  const inlineSample = hasInlineSampling(pythonCode, resolvedFlow, sampleCode);
  const effectiveSampleCode = resolveSampleCodeForExecution(
    sampleCode,
    { sampleSize, randomSeed },
    inlineSample,
  );

  useEffect(() => {
    if (skipSampleSyncRef.current) return undefined;
    const prev = prevSampleRef.current;
    if (prev.sampleSize === sampleSize && prev.randomSeed === randomSeed) return undefined;
    prevSampleRef.current = { sampleSize, randomSeed };

    const flowBase = originalFlowRef.current || resolvedFlow;
    if (!hasInlineSampling(pythonCodeRef.current, flowBase, sampleCodeRef.current)) return undefined;

    skipSampleSyncRef.current = true;
    let cancelled = false;

    const synced = resolveSampleCodeForExecution(
      sampleCodeRef.current,
      { sampleSize, randomSeed },
      true,
    );
    setSampleCode(synced);

    (async () => {
      try {
        const params = { sampleSize, randomSeed };
        if (hasInlineSamplingInFlow(flowBase)) {
          const patchedFlow = patchFlowSample(flowBase, params);
          if (originalFlowRef.current) {
            originalFlowRef.current = patchedFlow;
          }
          const res = await api.compileFlow({ flow: patchedFlow, target: 'sample_function' });
          if (!cancelled && res.success && res.python_code) {
            setSampleCode(res.python_code);
          }
        }
      } catch {
        /* synced fallback already applied */
      } finally {
        skipSampleSyncRef.current = false;
      }
    })();

    return () => { cancelled = true; };
  }, [sampleSize, randomSeed]);

  useEffect(() => {
    if (skipSampleSyncRef.current || !sampleCode) return undefined;
    const extracted = extractSampleFromSampleCode(sampleCode);
    if (!extracted) return undefined;

    const timer = setTimeout(() => {
      skipSampleSyncRef.current = true;
      patchQueryEnvSample({ sampleSize: extracted.sampleSize, randomSeed: extracted.randomSeed });
      prevSampleRef.current = { sampleSize: extracted.sampleSize, randomSeed: extracted.randomSeed };
      if (originalFlowRef.current && hasInlineSamplingInFlow(originalFlowRef.current)) {
        originalFlowRef.current = patchFlowSample(originalFlowRef.current, extracted);
      }
      skipSampleSyncRef.current = false;
    }, 400);

    return () => clearTimeout(timer);
  }, [sampleCode]);

  const buildBody = useCallback(async (overrides = {}) => {
    const wantsInline = hasInlineSampling(pythonCode, resolvedFlow, sampleCode);
    const fullProcessPreview = shouldUseFullProcessPreview({
      pythonCode,
      sampleCode,
      flow: resolvedFlow,
      filterMode,
      processPipeline,
    });
    const effectiveSample = resolveSampleCodeForExecution(
      sampleCode,
      { sampleSize, randomSeed },
      wantsInline,
    );
    const flowForRequest = wantsInline && resolvedFlow?.nodes?.length
      ? patchFlowSample(resolvedFlow, { sampleSize, randomSeed })
      : (filterMode === 'code' ? null : resolvedFlow);
    return {
      sql: overrides.sql ?? sql,
      start_time: formatSqlTime(toDatetimeLocalValue(queryEnv.START_TIME), false),
      end_time: formatSqlTime(toDatetimeLocalValue(queryEnv.END_TIME), true),
      strategy_id: loadedPresetId || undefined,
      env_schema: envSchema.length ? envSchema : undefined,
      filter_mode: uiBackendMode === 'code' ? 'code' : 'flow',
      flow: flowForRequest,
      python_code: pythonCode,
      sample_code: effectiveSample,
      filter_rules_code: await resolveFilterRulesCode(),
      preview_mode: fullProcessPreview ? 'full' : 'rules',
      process_pipeline: processPipeline.length ? processPipeline : undefined,
      data_source: dataSource,
      env: queryEnv,
      ...(dataSource === 'predict_result' && predictJobId ? { predict_job_id: predictJobId } : {}),
    };
  }, [sql, loadedPresetId, envSchema, uiBackendMode, filterMode, resolvedFlow, pythonCode, sampleCode, studio, dataSource, queryEnv, predictJobId, sampleSize, randomSeed, resolveFilterRulesCode, processPipeline]);

  const handleQueryJobDone = useCallback(async (job, meta) => {
    if (!meta) return;
    if (job.status === 'failed') return;
    if (job.status !== 'done') return;
    const count = Number(job.count) || 0;
    const stratName = meta?.stratName || job.label || '自由查询';
    const summary = `${stratName} · ${count} 条`;

    const consoleContent = job.console_output || job.execution_time != null
      ? {
          text: ['✓ 筛选完成', formatConsoleSummary({
            executionTime: job.execution_time,
            inputRows: job.input_rows,
            outputRows: job.output_rows,
          })].filter(Boolean).join('\n\n'),
          type: 'success',
          consoleOutput: job.console_output || '',
        }
      : {
          text: job.message || summary,
          type: 'success',
          consoleOutput: '',
        };

    saveHistoryEntry(buildHistoryEntry({
      strategy: stratName,
      strategyId: loadedPresetId,
      start: formatSqlTime(toDatetimeLocalValue(queryEnv.START_TIME), false),
      end: formatSqlTime(toDatetimeLocalValue(queryEnv.END_TIME), true),
      startRaw: toDatetimeLocalValue(queryEnv.START_TIME),
      endRaw: toDatetimeLocalValue(queryEnv.END_TIME),
      count,
      sampleSize: meta?.sampleSize ?? sampleSize,
      randomSeed: meta?.randomSeed ?? randomSeed,
      snapshot: meta?.snapshot,
      result: { task_id: job.task_id, count },
      summary,
      modeLabel: filterMode === 'rules' ? '规则' : '代码',
    }));

    if (job.task_id && count > 0) {
      saveLastQueryTaskId(job.task_id);
      navigate(buildQueryResultsPath(job.task_id), { state: { console: consoleContent } });
      try {
        const cfgRes = await api.getConfig();
        const cfg = cfgRes.config || {};
        if (cfg.viz_available) {
          const mode = cfg.viz_open_mode || 'prompt';
          if (mode === 'auto' && count <= 50) {
            await openSampleGalleryWhenReady(
              () => api.vizOpen({ source: 'query_task', task_id: job.task_id, dataset_name: summary }),
              '查询结果',
              {
                newWindow: viewerOpenNewWindowRef.current,
                taskId: job.task_id,
                returnTo: buildQueryResultsReturnPath(job.task_id),
              },
            );
          }
        }
      } catch { /* optional */ }
      return;
    }

    navigate('/query-results', {
      state: {
        console: consoleContent,
        summary: job.message || (count === 0 ? '无结果' : summary),
        empty: true,
      },
    });
  }, [
    navigate, loadedPresetId, queryEnv, sampleSize, randomSeed, filterMode,
  ]);

  const onPreview = async () => {
    let batch = null;
    try {
      if (dataSource === 'predict_result') batch = await ensurePredictBatchReady();
    } catch (e) {
      showErrorModal(e.message, { title: '预览失败' });
      return;
    }
    if (sqlNeedsTimeRange(sql, dataSource, batch?.jobId ?? predictJobId) && !envTimeReady(queryEnv)) {
      showErrorModal('请在策略参数中填写开始/结束时间', { title: '无法预览' });
      return;
    }
    if (!(await ensureFilterRulesReady())) return;
    setPreviewLoading(true);
    try {
      const res = await api.previewFilter(await buildBody(batch ? { sql: batch.sql } : {}));
      if (!res.success) throw new Error(res.error);
      const afterLabel = res.preview_mode === 'full' ? 'process_data 后' : '规则后';
      const parts = [`SQL ${res.sql_rows} 行`, `${afterLabel} ${res.filter_rows} 行`];
      if (res.preview_mode === 'full') {
        parts.push(`输出 ${res.after_sample} 条`);
      } else {
        parts.push(res.post_sample_skipped ? `已含代码采样 ${res.after_sample} 条` : `采样约 ${res.after_sample} 条`);
      }
      if (res.unique_products != null) parts.push(`${res.unique_products} 个产品`);
      if (res.execution_time != null) parts.push(`${res.execution_time}s`);
      const text = parts.join(' · ');
      setPreviewStats(text);
      setPreviewStale(false);
      if (res.console_output || res.execution_time != null) {
        const summary = formatConsoleSummary({
          executionTime: res.execution_time,
          inputRows: res.sql_rows,
          outputRows: res.filter_rows,
        });
        const previewDoneLabel = res.preview_mode === 'full' ? 'process_data 预览完成' : '预览完成';
        setConsole({
          text: [`✓ ${previewDoneLabel}`, summary].filter(Boolean).join('\n\n'),
          type: 'success',
          consoleOutput: res.console_output || '',
        });
      } else {
        setConsole({ text: `✓ 预览完成 · ${text}`, type: 'success', consoleOutput: '' });
      }
    } catch (e) { showErrorModal(e.message, { title: '预览失败' }); }
    finally { setPreviewLoading(false); }
  };

  const onExecuteRef = useRef(null);
  const onExecute = async () => {
    let batch = null;
    try {
      if (dataSource === 'predict_result') batch = await ensurePredictBatchReady();
    } catch (e) {
      showErrorModal(e.message, { title: '无法执行查询' });
      return;
    }
    if (sqlNeedsTimeRange(sql, dataSource, batch?.jobId ?? predictJobId) && !envTimeReady(queryEnv)) {
      showErrorModal('请在策略参数中填写开始/结束时间', { title: '无法执行查询' });
      return;
    }
    if (!(await ensureFilterRulesReady())) return;
    if (previewStale && studio.rules.length && !window.confirm('筛选条件未预览，仍要执行？')) return;
    const stratName = loadedPresetId ? (strategies.find((s) => s.id === loadedPresetId)?.name || loadedPresetId) : '自由查询';
    const wantsInline = hasInlineSampling(pythonCode, resolvedFlow, sampleCode);
    const effectiveSampleCode = resolveSampleCodeForExecution(
      sampleCode,
      { sampleSize, randomSeed },
      wantsInline,
    );
    const jobMeta = {
      stratName,
      sampleSize,
      randomSeed,
      snapshot: {
        sql_template: sql,
        python_code: pythonCode,
        sample_code: effectiveSampleCode,
        filter_mode: uiBackendMode,
        flow: resolvedFlow,
        sample_size: sampleSize,
        random_seed: randomSeed,
      },
    };
    setSubmitting(true);
    try {
      const body = await buildBody(batch ? { sql: batch.sql } : {});
      const submitOnce = () => submitQueryJob(body, { label: stratName, meta: jobMeta });
      try {
        await submitOnce();
      } catch (e) {
        if (e?.isNetwork || /无法连接后端/i.test(e.message || '')) {
          await new Promise((r) => setTimeout(r, 2000));
          await submitOnce();
        } else {
          throw e;
        }
      }
      showInfoModal('查询已提交后台执行；完成后将自动打开「查询结果」页。可继续调整条件或切换页面。', { title: '已提交' });
    } catch (e) {
      showErrorModal(e.message, { title: '提交查询失败' });
    } finally {
      setSubmitting(false);
    }
  };
  onExecuteRef.current = onExecute;

  useEffect(() => {
    const onJobFinished = (e) => {
      const { job, meta } = e.detail || {};
      if (!job || !meta) return;
      handleQueryJobDone(job, meta);
    };
    window.addEventListener('pc-query-job-finished', onJobFinished);
    return () => window.removeEventListener('pc-query-job-finished', onJobFinished);
  }, [handleQueryJobDone]);

  useEffect(() => {
    if (!pendingAutoExecJobId || dataSource !== 'predict_result') return undefined;
    if (predictJobId !== pendingAutoExecJobId) return undefined;
    if (!sql.includes(`job_id = ${pendingAutoExecJobId}`)) return undefined;
    setPendingAutoExecJobId(null);
    const timer = setTimeout(() => onExecuteRef.current?.(), 80);
    return () => clearTimeout(timer);
  }, [pendingAutoExecJobId, predictJobId, sql, dataSource]);

  useEffect(() => {
    const onKey = (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') { e.preventDefault(); onExecute(); } };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  async function loadStrategy(id) {
    if (!id) {
      setLoadedPresetId('');
      originalFlowRef.current = null;
      localStorage.setItem('pc_last_preset', '__free__');
      studio.setFlow({ version: 2, nodes: [] });
      setFilterMode('rules');
      setPythonCode(DEFAULT_PY);
      setSampleCode('');
      setQueryEnv({});
      setEnvSchema([]);
      setProcessPipeline([]);
      savedFilterRulesCodeRef.current = '';
      setQueryUiMode(loadQueryUiModePreference());
      setCompactHide(defaultCompactHideMap());
      return;
    }
    const res = await api.getStrategy(id);
    if (!res.success) { toast(res.error, 'error'); return; }
    const s = res.data;
    setQueryUiMode(resolveQueryUiMode(s));
    setCompactHide(resolveCompactHideMap(s));
    setLoadedPresetId(id);
    originalFlowRef.current = s.flow ? JSON.parse(JSON.stringify(s.flow)) : null;
    savedFilterRulesCodeRef.current = s.filter_rules_code || '';
    localStorage.setItem('pc_last_preset', id);
    const ds = inferDataSourceFromStrategy(s);
    setDataSource(ds);
    if (ds === 'predict_result') {
      setPredictJobsLoading(true);
      try {
        const recent = await fetchRecentPredictJobs(api);
        setPredictJobs(recent);
        const preferred = parseDefaultPredictJobId(s);
        const jobId = preferred || await resolvePredictJobId({
          urlJobId: searchParams.get('predict_job'),
          recentJobs: recent,
        });
        await applyPredictBatchSql(jobId, { silent: true });
      } catch (e) {
        toast(e.message, 'error');
      } finally {
        setPredictJobsLoading(false);
      }
    } else {
      setSql(s.sql_template || DEFAULT_DETAIL_SQL);
      setPredictJobId(null);
    }
    const varsRes = await api.getStrategyVariables(id).catch(() => null);
    const schema = (varsRes?.data?.custom_vars || []).map((row) => {
      const key = String(row?.key || '').toUpperCase();
      if (key === 'START_TIME' || key === 'END_TIME') return { ...row, type: 'datetime' };
      return row;
    });
    const defaults = varsRes?.data?.env_defaults || {};
    setEnvSchema(schema);
    setQueryEnv(buildStrategyEnvDefaults(schema, s, { ...loadStrategyEnv(id), ...defaults }));
    const split = splitStrategyPython({
      pythonCode: s.python_code,
      sampleCode: s.sample_code,
    });
    let proc = normalizeProcessSampleCall(split.processCode || DEFAULT_PY);
    let sample = split.sampleCode || '';
    if (!sample && hasInlineSamplingInFlow(s.flow)) {
      const compiled = await api.compileFlow({ flow: s.flow, target: 'sample_function' });
      if (compiled.success && compiled.python_code) sample = compiled.python_code;
    }
    setPythonCode(proc);
    setSampleCode(sample);
    const sampleSettings = resolveSampleSettings({
      pythonCode: proc,
      sampleCode: sample,
      flow: s.flow,
      sampleSize: s.sample_size,
      randomSeed: s.random_seed,
    });
    skipSampleSyncRef.current = true;
    patchQueryEnvSample({
      sampleSize: sampleSettings.sampleSize,
      randomSeed: sampleSettings.randomSeed,
    });
    prevSampleRef.current = { sampleSize: sampleSettings.sampleSize, randomSeed: sampleSettings.randomSeed };
    queueMicrotask(() => { skipSampleSyncRef.current = false; });
    setFilterMode(uiFilterMode(s.filter_mode || 'flow'));
    setProcessPipeline(Array.isArray(s.process_pipeline) ? s.process_pipeline : []);
    if (s.flow) {
      studio.setFlow(s.flow, {
        removeEmptyRows: s.remove_empty_rows,
        filterRulesCode: s.filter_rules_code,
      });
    }
    markStale();
  }

  const buildStrategyPayload = async (name, id) => ({
    schema_version: 2,
    id: id || loadedPresetId || `saved_${Date.now()}`,
    name,
    category: '我的查询',
    description: '从主界面保存',
    sql_template: sql,
    python_code: pythonCode,
    sample_code: resolveSampleCodeForExecution(sampleCode, { sampleSize, randomSeed }, inlineSample),
    sample_size: sampleSize,
    random_seed: randomSeed,
    env_schema: envSchema,
    filter_mode: uiBackendMode,
    flow: resolvedFlow || { version: 2, nodes: [] },
    remove_empty_rows: studio.removeEmpty,
    filter_rules_code: await resolveFilterRulesCode(),
    query_ui_mode: queryUiMode,
    query_compact_hide: queryUiMode === QUERY_UI_MODE_COMPACT
      ? serializeCompactHideForSave(compactHide)
      : undefined,
    process_pipeline: processPipeline.length ? processPipeline : undefined,
    data_source: dataSource,
    ...(dataSource === 'predict_result' && predictJobId
      ? { default_predict_job_id: predictJobId }
      : {}),
  });

  const confirmSave = async () => {
    if (!saveName.trim()) {
      showErrorModal('请输入策略名称', { title: '无法保存' });
      return;
    }
    try {
      const payload = await buildStrategyPayload(saveName.trim());
      const res = await api.saveStrategy(payload);
      if (!res.success) throw new Error(res.error);
      setSaveOpen(false);
      setLoadedPresetId(payload.id);
      originalFlowRef.current = payload.flow ? JSON.parse(JSON.stringify(payload.flow)) : null;
      localStorage.setItem('pc_last_preset', payload.id);
      await reloadStrategies();
      if (loadedPresetId === payload.id) await loadStrategy(payload.id);
      showResultModal(`策略「${saveName.trim()}」已保存`, { title: '保存成功' });
    } catch (e) {
      showErrorModal(e.message, { title: '保存失败' });
    }
  };

  const exportStrategy = async () => {
    const payload = await buildStrategyPayload(strategies.find((s) => s.id === loadedPresetId)?.name || 'export', loadedPresetId || `export_${Date.now()}`);
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${payload.id}.json`;
    a.click();
  };

  const importStrategy = async (file) => {
    if (!file) return;
    try {
      const raw = JSON.parse(await file.text());
      if (!raw.id || !raw.sql_template) throw new Error('缺少 id 或 sql_template');
      const data = prepareImportedStrategy(raw);
      const res = await api.saveStrategy(data);
      if (!res.success) throw new Error(res.error);
      await reloadStrategies();
      loadStrategy(data.id);
      toast('策略已导入');
    } catch (e) { toast(e.message, 'error'); }
  };

  const runPythonTest = async () => {
    try {
      const parts = [];
      if (filterMode !== 'code') parts.push(await resolveFilterRulesCode());
      const sampleForRun = resolveSampleCodeForExecution(
        sampleCode,
        { sampleSize, randomSeed },
        hasInlineSampling(pythonCode, resolvedFlow, sampleCode),
      );
      if (sampleForRun) parts.push(sampleForRun);
      parts.push(pythonCode);
      const code = parts.filter(Boolean).join('\n\n');
      const res = await api.runPython({ python_code: code });
      if (!res.success) throw new Error(res.error);
      const summary = formatConsoleSummary({
        executionTime: res.execution_time,
        inputRows: res.input_rows,
        outputRows: res.output_rows,
      });
      setConsole({
        text: [res.message, summary].filter(Boolean).join('\n\n'),
        type: 'success',
        consoleOutput: res.console_output || '',
      });
    } catch (e) {
      showErrorModal(e.message, { title: 'Python 运行失败' });
    }
  };

  const savePythonLocal = () => {
    localStorage.setItem('pc_python', pythonCode);
    toast('Python 已保存到本地');
  };

  const loadPythonLocal = () => {
    const saved = localStorage.getItem('pc_python');
    if (!saved) { toast('本地无已保存的 Python', 'error'); return; }
    if (pythonCode !== saved && !window.confirm('用本地保存的代码覆盖当前内容？')) return;
    setPythonCode(saved);
    toast('已加载本地 Python');
  };

  const loadPythonFile = async (file) => {
    if (!file) return;
    try {
      const text = await file.text();
      setPythonCode(text);
      toast('已从文件加载 Python');
    } catch (e) { toast(e.message, 'error'); }
  };

  const onChangeDataSource = async (value) => {
    setDataSource(value);
    if (value === 'predict_result') {
      try {
        setPredictJobsLoading(true);
        const recent = await fetchRecentPredictJobs(api);
        setPredictJobs(recent);
        const jobId = await resolvePredictJobId({ urlJobId: searchParams.get('predict_job'), recentJobs: recent });
        await applyPredictBatchSql(jobId, { silent: !jobId });
        if (!jobId) toast('已切换到预测结果表');
      } catch (e) { toast(e.message, 'error'); }
      finally { setPredictJobsLoading(false); }
    } else {
      setSql(DEFAULT_DETAIL_SQL);
      toast('已切换到检测明细表');
    }
    markStale();
  };

  useEffect(() => {
    if (initialQuery.dataSource !== 'predict_result') return undefined;
    let cancelled = false;
    (async () => {
      setPredictJobsLoading(true);
      try {
        const recent = await fetchRecentPredictJobs(api);
        if (cancelled) return;
        setPredictJobs(recent);
        const jobId = await resolvePredictJobId({
          urlJobId: searchParams.get('predict_job'),
          sql: localStorage.getItem('pc_sql') || sql,
          recentJobs: recent,
        });
        if (!jobId) return;
        await applyPredictBatchSql(jobId, { silent: !searchParams.get('predict_job') });
        const urlJob = searchParams.get('predict_job');
        if (urlJob) {
          const job = recent.find((j) => j.id === jobId);
          toast(`已载入预测批次 ${formatPredictJobLabel(job || { id: jobId })}`);
          setPendingAutoExecJobId(jobId);
        }
      } catch { /* keep current SQL */ }
      finally {
        if (!cancelled) setPredictJobsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  useEffect(() => {
    if (dataSource !== 'predict_result') return undefined;
    let cancelled = false;
    let timer;
    const poll = async () => {
      try {
        const recent = await fetchRecentPredictJobs(api);
        if (cancelled) return;
        setPredictJobs(recent);
        const active = recent.some((j) => j.status === 'running' || j.status === 'pending');
        timer = setTimeout(poll, active ? 1500 : 8000);
      } catch {
        if (!cancelled) timer = setTimeout(poll, 8000);
      }
    };
    timer = setTimeout(poll, 1500);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [dataSource]);

  const complexFlow = hasComplexFlow(originalFlowRef.current);

  const selectedPredictJob = useMemo(
    () => predictJobs.find((j) => j.id === predictJobId) || null,
    [predictJobs, predictJobId],
  );

  const queryModeHint = (() => {
    if (dataSource === 'predict_result' && predictJobId) {
      const name = selectedPredictJob?.name || selectedPredictJob?.params?.model_name;
      return `预测结果 · 批次 #${predictJobId}${name ? ` · ${name}` : ''}`;
    }
    const modeLabel = { rules: '规则筛选', code: 'Python 筛选' }[filterMode] || '规则筛选';
    const prefix = loadedPresetId
      ? (strategies.find((s) => s.id === loadedPresetId)?.name || '策略')
      : '自由查询';
    const viewLabel = queryUiModeLabel(queryUiMode);
    const compactRules = showCompactFilterRules(compactHide, queryUiMode);
    return queryUiMode === QUERY_UI_MODE_COMPACT
      ? `${prefix} · ${viewLabel} · 参数${compactRules ? ' + 规则' : ''}`
      : `${prefix} · ${viewLabel} · SQL + ${modeLabel}`;
  })();

  const sampleSizeHint = inlineSample
    ? (sampleSize != null
      ? `策略流 random_sample · process_data 内采样 · SAMPLE_SIZE=${sampleSize} · RANDOM_SEED=${randomSeed}`
      : '策略流已选 random_sample · 请在策略参数填写 SAMPLE_SIZE 后才会执行采样')
    : '未在策略流中选择 random_sample · 不随机采样（时间窗 START/END 除外，其余走环境变量）';

  const sqlVarHint = useMemo(() => {
    const used = extractSqlTemplateVars(sql);
    const parts = [];
    for (const key of used) {
      if (RUNTIME_VAR_LABELS[key]) {
        parts.push(`${RUNTIME_VAR_LABELS[key].replace(/（.*?）/, '')}→\${${key}}`);
      } else {
        const row = envSchema.find((r) => r.key === key);
        const label = row?.label && row.label !== key ? row.label : key;
        parts.push(`${label}→\${${key}}`);
      }
    }
    if (!parts.length) {
      return '${START_TIME} · ${END_TIME} · 策略参数…';
    }
    return parts.join(' · ');
  }, [sql, envSchema]);

  const replayStage = searchParams.get('replay_stage');
  const replayStageLabel = replayStage === '1' ? '历史回跑 · Stage1 历史查询'
    : replayStage === '2' ? '历史回跑 · Stage2 预测后筛选' : null;

  return (
    <div className="panel active" id="panel-query">
      {replayStageLabel && (
        <div className="query-replay-banner" data-testid="query-replay-banner">
          {replayStageLabel} — 在此调整 SQL / 筛选规则；时段在工具栏，其余参数见策略可调参数
        </div>
      )}
      <div className="topbar">
        <div className="topbar-left-group">
          <SceneHubNav variant="query" className="scene-hub-nav-inline" />
          <div>
            <div className="topbar-title">数据查询</div>
            <div className="topbar-sub" id="query-mode-hint">{queryModeHint}</div>
          </div>
          <StrategyPicker
            strategies={strategies}
            value={loadedPresetId}
            onSelect={loadStrategy}
            onImportClick={() => importRef.current?.click()}
            onDeleteRequest={setDeleteId}
          />
          {!shouldHideInCompact(compactHide, 'strategy_tools', queryUiMode) && (
            <>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setSaveName(strategies.find((s) => s.id === loadedPresetId)?.name || ''); setSaveOpen(true); }}>保存</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={exportStrategy}>导出</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => importRef.current?.click()}>导入</button>
              <input ref={importRef} type="file" accept=".json" hidden onChange={(e) => { importStrategy(e.target.files?.[0]); e.target.value = ''; }} />
              {loadedPresetId && (
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setDeleteId(loadedPresetId)}>删除</button>
              )}
            </>
          )}
        </div>
        <div className="topbar-actions query-topbar-actions">
          {!shouldHideInCompact(compactHide, 'preview_button', queryUiMode) && (
            <button
              type="button"
              className={`btn btn-sm btn-secondary${previewStale ? ' is-recommended' : ''}`}
              disabled={previewLoading}
              onClick={onPreview}
            >
              {previewLoading ? '预览中…' : '预览筛选'}
            </button>
          )}
          <button
            type="button"
            className={`btn btn-sm btn-primary${previewStale && studio.rules.length ? ' needs-preview' : ''}`}
            disabled={submitting || previewLoading}
            onClick={onExecute}
            data-testid="query-execute"
            title="Ctrl + Enter 执行查询"
          >
            {submitting ? '提交中…' : runningCount > 0 ? `执行查询（${runningCount}）` : '执行查询'}
          </button>
          <div className="query-ui-mode-switch" role="group" aria-label="查询页视图">
            {QUERY_UI_MODE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`query-ui-mode-btn${queryUiMode === opt.id ? ' is-active' : ''}`}
                title={opt.description}
                onClick={() => setQueryUiModePersist(opt.id)}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="panel-scroll">
        <div className="section section-query">
          <div
            className={`query-setup${queryUiMode === QUERY_UI_MODE_COMPACT ? ' is-compact' : ''}`}
            id="query-setup"
          >
          <div className="controls-card">
            {!shouldHideInCompact(compactHide, 'data_source', queryUiMode) && (
            <div className="control-inline control-source">
              <label htmlFor="data-source">数据源</label>
              <select id="data-source" value={dataSource} onChange={(e) => onChangeDataSource(e.target.value)}>
                <option value="predict_result">预测结果表</option>
                <option value="detail">检测明细表</option>
              </select>
            </div>
            )}
            {!shouldHideInCompact(compactHide, 'predict_job', queryUiMode) && dataSource === 'predict_result' && (
              <div className="control-inline control-predict-job">
                <label htmlFor="predict-job-id">预测批次</label>
                <select
                  id="predict-job-id"
                  value={predictJobId ?? ''}
                  disabled={predictJobsLoading || !predictJobs.length}
                  onChange={async (e) => {
                    const jobId = Number(e.target.value);
                    if (!jobId) return;
                    try {
                      await applyPredictBatchSql(jobId, { silent: true });
                    } catch (err) { toast(err.message, 'error'); }
                  }}
                >
                  {!predictJobs.length && <option value="">暂无预测作业</option>}
                  {predictJobs.map((j) => (
                    <option key={j.id} value={j.id}>
                      {formatPredictJobLabel(j)}
                    </option>
                  ))}
                </select>
                <span className="muted predict-job-hint">
                  {predictJobsLoading
                    ? '匹配中…'
                    : selectedPredictJob
                      ? '无需时段'
                      : '自动匹配最近批次，可手动切换'}
                </span>
              </div>
            )}
            {!shouldHideInCompact(compactHide, 'strategy_params', queryUiMode) && showStrategyEnv && (
            <StrategyEnvFields
              strategyId={loadedPresetId}
              schema={displayEnvSchema}
              values={queryEnv}
              onChange={(env) => {
                setQueryEnv(env);
                if (loadedPresetId) saveStrategyEnv(loadedPresetId, env);
                markStale();
              }}
              compact
              testId="query-env-section"
            />
            )}
          </div>

          {showCompactFilterRules(compactHide, queryUiMode) && (
            <section className="query-compact-rules" aria-label="筛选规则">
              <header className="query-compact-rules-head">
                <span className="query-compact-rules-title">筛选规则</span>
                <span className="muted query-compact-rules-sub">简洁模式仅可编辑规则，不可切换代码</span>
              </header>
              <div className="query-compact-rules-body">
                {filterMode === 'code' && !studio.rules.length ? (
                  <p className="muted query-compact-rules-code-hint">
                    当前策略为代码筛选模式，规则表不可用；请切换到
                    {' '}
                    <button type="button" className="btn-link" onClick={() => setQueryUiModePersist(QUERY_UI_MODE_FULL)}>完整</button>
                    {' '}
                    视图或到
                    {loadedPresetId ? <Link to="/strategies"> 策略编辑</Link> : ' 策略编辑'}
                    修改。
                  </p>
                ) : (
                  <RulesBuilder studio={studio} complexHint={complexFlow} keyboardActive />
                )}
              </div>
            </section>
          )}

          {queryUiMode === QUERY_UI_MODE_COMPACT && !shouldHideInCompact(compactHide, 'compact_hint', queryUiMode) && (
            <div className="query-compact-hint">
              <span className="muted">
                简洁模式：填参数
                {showCompactFilterRules(compactHide, queryUiMode) ? '、调规则' : ''}
                并执行；SQL
                {showCompactFilterRules(compactHide, queryUiMode) ? ' / 代码' : ' / 规则 / 代码'}
                在
                {loadedPresetId ? (
                  <Link to="/strategies">策略编辑</Link>
                ) : (
                  '策略'
                )}
                中维护。
              </span>
              {!shouldHideInCompact(compactHide, 'preview_stats', queryUiMode) && (previewStats || imgPathHint) && (
                <div className="query-compact-stats">
                  {previewStats && (
                    <span className={`preview-stats${previewStale ? ' is-stale' : ''}`}>{previewStale ? '条件已变更 · 请预览' : previewStats}</span>
                  )}
                  {imgPathHint && <span className="footer-hint is-warning">{imgPathHint}</span>}
                </div>
              )}
            </div>
          )}

          {queryUiMode === QUERY_UI_MODE_FULL && (
          <div className="workspace">
            {editorWs.fullscreenPane && (
              <div
                className="editor-fullscreen-backdrop"
                onClick={() => editorWs.toggleFullscreen(editorWs.fullscreenPane)}
                aria-hidden
              />
            )}
            <div
              className={`editor-workspace${editorWs.fullscreenPane ? ' editor-fullscreen-active' : ''}`}
              ref={editorWs.workspaceRef}
              style={{ '--editor-split-h': `${editorWs.height}px`, height: editorWs.fullscreenPane ? undefined : `${editorWs.height}px` }}
            >
              <div
                className="editor-split"
                ref={editorWs.splitRef}
                style={{ '--editor-sql-pct': `${editorWs.sqlPct}%` }}
              >
                <div
                  className={`editor-pane sql-pane${editorWs.fullscreenPane === 'sql' ? ' pane-fullscreen' : ''}`}
                  id="pane-sql"
                  ref={editorWs.sqlPaneRef}
                >
                  <div className="editor-pane-header editor-pane-header--sql">
                    <div className="editor-pane-header-row">
                      <span className="ep-title">SQL 查询</span>
                      <button type="button" className="ep-btn ep-icon" title={editorWs.fullscreenPane === 'sql' ? '退出全屏' : '全屏编辑'} onClick={() => editorWs.toggleFullscreen('sql')}>
                        <FullscreenIcon />
                      </button>
                    </div>
                    <div className="ep-hint-bar" title={sqlVarHint}>{sqlVarHint}</div>
                  </div>
                  <div className="editor-wrap"><SqlEditor value={sql} onChange={setSql} /></div>
                </div>
                <div className="editor-col-resize-handle" id="editor-col-resize-handle" title="拖拽调整左右占比">
                  <span className="resize-grip-v" />
                </div>
                <div className={`editor-pane python-pane${editorWs.fullscreenPane === 'python' ? ' pane-fullscreen' : ''}`} id="pane-python">
                  <div className="editor-pane-header">
                    <span className="ep-title">Python 筛选</span>
                    <div className="filter-mode-tabs">
                      {['rules', 'code'].map((m) => (
                        <button key={m} type="button" className={`filter-mode-tab${filterMode === m ? ' active' : ''}`} onClick={() => setFilterMode(m)}>
                          {({ rules: '规则', code: '代码' })[m]}
                        </button>
                      ))}
                    </div>
                    <div className="ep-header-right">
                      <div className="ep-actions">
                        <button type="button" className="ep-btn" onClick={() => setHelpOpen(true)}>帮助</button>
                        <button type="button" className="ep-btn" onClick={runPythonTest}>测试</button>
                        {filterMode === 'code' && (
                          <>
                            <button type="button" className="ep-btn" onClick={savePythonLocal}>保存</button>
                            <button type="button" className="ep-btn" onClick={loadPythonLocal}>加载</button>
                            <button type="button" className="ep-btn" onClick={() => pythonFileRef.current?.click()}>文件</button>
                            <input ref={pythonFileRef} type="file" accept=".py,.txt" hidden onChange={(e) => { loadPythonFile(e.target.files?.[0]); e.target.value = ''; }} />
                          </>
                        )}
                      </div>
                      <button type="button" className="ep-btn ep-icon" title={editorWs.fullscreenPane === 'python' ? '退出全屏' : '全屏编辑'} onClick={() => editorWs.toggleFullscreen('python')}>
                        <FullscreenIcon />
                      </button>
                    </div>
                  </div>
                  <div className="python-pane-body">
                    {filterMode === 'rules' && (
                      <div className="filter-panel filter-panel-rules">
                        <RulesBuilder studio={studio} complexHint={complexFlow} keyboardActive />
                      </div>
                    )}
                    {filterMode === 'code' && (
                      <div className="filter-panel filter-panel-code">
                        <PythonCodeWorkspace
                          pythonCode={pythonCode}
                          onPythonCodeChange={(v) => { setPythonCode(v); markStale(); }}
                          sampleCode={effectiveSampleCode}
                          filterRulesCode={studio.compiledCode}
                          showSample={inlineSample}
                          showFilterRules={studio.rules.length > 0}
                        />
                      </div>
                    )}
                  </div>
                </div>
              </div>
              {!editorWs.fullscreenPane && (
                <div className="editor-resize-handle" id="editor-resize-handle" title="拖拽调整编辑器高度">
                  <span className="resize-grip" />
                </div>
              )}
            </div>
            <div className="workspace-footer">
              <span className={`footer-hint${filterMode !== 'code' ? ' is-warning' : ''}`} id="sample-size-hint">{sampleSizeHint}</span>
              {previewStats && <span className={`preview-stats${previewStale ? ' is-stale' : ''}`} id="preview-stats">{previewStale ? '条件已变更 · 请预览' : previewStats}</span>}
              {imgPathHint && <span className="footer-hint is-warning" id="img-path-hint">{imgPathHint}</span>}
            </div>
          </div>
          )}
          </div>
        </div>
      </div>

      <ConsolePanel
        visible={!!console}
        content={console}
        onClear={() => setConsole(null)}
      />

      <Modal open={saveOpen} title="保存为策略" onClose={() => setSaveOpen(false)}>
        <div className="form-modal-body">
          <label className="form-label">策略名称</label>
          <input className="form-input" value={saveName} onChange={(e) => setSaveName(e.target.value)} />
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setSaveOpen(false)}>取消</button>
            <button type="button" className="btn btn-primary" onClick={confirmSave}>保存</button>
          </div>
        </div>
      </Modal>

      <Modal open={helpOpen} title="Python 预设函数" wide onClose={() => setHelpOpen(false)}>
        <div className="help-body">{PYTHON_HELP.map(([k, v]) => <div key={k} className="help-item"><strong>{k}</strong><span>{v}</span></div>)}</div>
      </Modal>

      <Modal open={!!deleteId} title="删除策略" onClose={() => setDeleteId('')}>
        <div className="form-modal-body">
          <p>确定删除策略 {deleteId}？</p>
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setDeleteId('')}>取消</button>
            <button type="button" className="btn btn-danger" onClick={async () => {
              try {
                const res = await api.deleteStrategy(deleteId);
                if (!res.success) throw new Error(res.error);
                setDeleteId('');
                loadStrategy('');
                reloadStrategies();
                toast('已删除');
              } catch (e) {
                toast(e.message || '删除失败', 'error');
              }
            }}>删除</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
