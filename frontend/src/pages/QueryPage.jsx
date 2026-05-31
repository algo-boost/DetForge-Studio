import { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { api, formatSqlTime, toast, openSampleGalleryWhenReady } from '../api/client';
import { SqlEditor, PythonEditor } from '../components/Editors';
import { PythonCodeWorkspace } from '../components/PythonCodeWorkspace';
import { RulesBuilder } from '../components/RulesBuilder';
import { ResultsPanel } from '../components/ResultsPanel';
import { StrategyPicker } from '../components/StrategyPicker';
import SceneHubNav from '../components/SceneHubNav';
import { ConsolePanel, PYTHON_HELP } from '../components/ConsolePanel';
import { formatConsoleSummary } from '../lib/consoleOutput';
import { Modal } from '../components/Modal';
import { useRulesStudio } from '../hooks/useRulesStudio';
import { useEditorWorkspace, FullscreenIcon } from '../hooks/useEditorWorkspace';
import { DEFAULT_PY, DEFAULT_SAMPLE, DEFAULT_SEED, DEFAULT_SQL, DEFAULT_DETAIL_SQL, DEFAULT_PREDICT_SQL, buildPredictJobSql, buildSampleFunction } from '../lib/constants';
import { fetchRecentPredictJobs, parsePredictJobIdFromSql, resolvePredictJobId } from '../lib/predictJob';
import { buildHistoryEntry, saveHistoryEntry } from '../lib/history';
import { setTimePreset } from '../lib/time';
import { backendFilterMode, hasComplexFlow, mergeFlowForSave, uiFilterMode } from '../lib/flowMerge';
import {
  extractSampleFromSampleCode,
  hasInlineSampling,
  hasInlineSamplingInFlow,
  normalizeProcessSampleCall,
  patchFlowSample,
  patchSampleFunction,
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

export default function QueryPage() {
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const restored = useRef(false);
  const initialQuery = resolveInitialQueryState();
  const [sql, setSql] = useState(initialQuery.sql);
  const [pythonCode, setPythonCode] = useState(() => localStorage.getItem('pc_python') || DEFAULT_PY);
  const [sampleCode, setSampleCode] = useState('');
  const [filterMode, setFilterMode] = useState('rules');
  const [startTime, setStartTime] = useState('');
  const [endTime, setEndTime] = useState('');
  const [sampleSize, setSampleSize] = useState(DEFAULT_SAMPLE);
  const [randomSeed, setRandomSeed] = useState(() => {
    const saved = parseInt(localStorage.getItem('pc_random_seed') || '', 10);
    return Number.isFinite(saved) ? saved : DEFAULT_SEED;
  });
  const [strategies, setStrategies] = useState([]);
  const [dataSource, setDataSource] = useState(initialQuery.dataSource);
  const [predictJobId, setPredictJobId] = useState(null);
  const [predictJobs, setPredictJobs] = useState([]);
  const [predictJobsLoading, setPredictJobsLoading] = useState(false);
  const [loadedPresetId, setLoadedPresetId] = useState('');
  const originalFlowRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [previewStats, setPreviewStats] = useState('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewStale, setPreviewStale] = useState(true);
  const [imgPathHint, setImgPathHint] = useState('');
  const [rawResults, setRawResults] = useState([]);
  const [taskId, setTaskId] = useState('');
  const [executionDetail, setExecutionDetail] = useState(null);
  const [console, setConsole] = useState(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [saveName, setSaveName] = useState('');
  const [helpOpen, setHelpOpen] = useState(false);
  const [deleteId, setDeleteId] = useState('');
  const importRef = useRef(null);
  const pythonFileRef = useRef(null);
  const skipSampleSyncRef = useRef(false);
  const prevSampleRef = useRef({ sampleSize: DEFAULT_SAMPLE, randomSeed: DEFAULT_SEED });
  const pythonCodeRef = useRef(pythonCode);
  const sampleCodeRef = useRef(sampleCode);
  pythonCodeRef.current = pythonCode;
  sampleCodeRef.current = sampleCode;

  const markStale = useCallback(() => setPreviewStale(true), []);
  const studio = useRulesStudio(markStale);
  const editorWs = useEditorWorkspace();

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
    if (snap.flow) studio.setFlow(snap.flow);
    const sample = resolveSampleSettings({
      pythonCode: split.processCode,
      sampleCode: snap.sample_code || split.sampleCode,
      flow: snap.flow,
      sampleSize: snap.sample_size,
      randomSeed: snap.random_seed,
    });
    skipSampleSyncRef.current = true;
    prevSampleRef.current = { sampleSize: sample.sampleSize, randomSeed: sample.randomSeed };
    setSampleSize(sample.sampleSize);
    setRandomSeed(sample.randomSeed);
    queueMicrotask(() => { skipSampleSyncRef.current = false; });
    markStale();
  }, [studio, markStale]);

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
    setStartTime(p.start);
    setEndTime(p.end);
    refreshPathChecks(true);
    reloadStrategies();
    const last = localStorage.getItem('pc_last_preset');
    if (last && last !== '__free__') loadStrategy(last);
    else loadStrategy('daily_trawl');
  }, []);

  useEffect(() => {
    if (restored.current || !location.state?.restore) return;
    restored.current = true;
    const item = location.state.restore;
    if (item.start_raw) setStartTime(item.start_raw);
    if (item.end_raw) setEndTime(item.end_raw);
    if (item.snapshot) applySnapshot(item.snapshot);
    else if (item.strategy_id) loadStrategy(item.strategy_id);
    if (item.sample_size != null) setSampleSize(item.sample_size);
    if (item.random_seed != null) setRandomSeed(item.random_seed);
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
    const recent = predictJobs.length ? predictJobs : await fetchRecentPredictJobs();
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

  useEffect(() => { localStorage.setItem('pc_random_seed', String(randomSeed)); markStale(); }, [randomSeed, markStale]);

  const uiBackendMode = backendFilterMode(filterMode);
  const flowPayload = filterMode === 'code' ? null : studio.flow;
  const resolvedFlow = mergeFlowForSave(originalFlowRef.current, flowPayload);
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
      if (extracted.sampleSize !== sampleSize) setSampleSize(extracted.sampleSize);
      if (extracted.randomSeed !== randomSeed) setRandomSeed(extracted.randomSeed);
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
      start_time: formatSqlTime(startTime, false),
      end_time: formatSqlTime(endTime, true),
      sample_size: sampleSize,
      random_seed: randomSeed,
      filter_mode: uiBackendMode === 'code' ? 'code' : 'flow',
      flow: flowForRequest,
      python_code: pythonCode,
      sample_code: effectiveSample,
      filter_rules_code: await studio.compile(),
      preview_mode: wantsInline || filterMode === 'code' ? 'full' : 'rules',
      data_source: dataSource,
    };
  }, [sql, startTime, endTime, sampleSize, randomSeed, uiBackendMode, filterMode, resolvedFlow, pythonCode, sampleCode, studio, dataSource]);

  const onPreview = async () => {
    let batch = null;
    try {
      if (dataSource === 'predict_result') batch = await ensurePredictBatchReady();
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
    if (sqlNeedsTimeRange(sql, dataSource, batch?.jobId ?? predictJobId) && (!startTime || !endTime)) {
      toast('请选择查询时段', 'error');
      return;
    }
    setPreviewLoading(true);
    try {
      const res = await api.previewFilter(await buildBody(batch ? { sql: batch.sql } : {}));
      if (!res.success) throw new Error(res.error);
      const parts = [`SQL ${res.sql_rows} 行`, `规则后 ${res.filter_rows} 行`];
      parts.push(res.post_sample_skipped ? `已含代码采样 ${res.after_sample} 条` : `采样约 ${res.after_sample} 条`);
      if (res.unique_products != null) parts.push(`${res.unique_products} 个产品`);
      const text = parts.join(' · ');
      setPreviewStats(text);
      setPreviewStale(false);
      setExecutionDetail({ summary: `预览 · ${text}`, detail: JSON.stringify(res, null, 2) });
      toast(text);
    } catch (e) { toast(e.message, 'error'); }
    finally { setPreviewLoading(false); }
  };

  const onExecuteRef = useRef(null);
  const onExecute = async () => {
    let batch = null;
    try {
      if (dataSource === 'predict_result') batch = await ensurePredictBatchReady();
    } catch (e) {
      toast(e.message, 'error');
      return;
    }
    if (sqlNeedsTimeRange(sql, dataSource, batch?.jobId ?? predictJobId) && (!startTime || !endTime)) {
      toast('请选择查询时段', 'error');
      return;
    }
    if (previewStale && studio.rules.length && !window.confirm('筛选条件未预览，仍要执行？')) return;
    setLoading(true);
    setRawResults([]);
    try {
      const res = await api.query(await buildBody(batch ? { sql: batch.sql } : {}));
      if (!res.success) throw new Error(res.error);
      const data = res.data || [];
      setRawResults(data);
      setTaskId(res.task_id || '');
      const stratName = loadedPresetId ? (strategies.find((s) => s.id === loadedPresetId)?.name || loadedPresetId) : '自由查询';
      const summary = `${stratName} · ${data.length} 条`;
      setExecutionDetail({
        summary,
        detail: JSON.stringify({ input: res.input_rows, output: res.output_rows, sample: res.sample_size, skipped: res.post_sample_skipped }, null, 2),
      });
      if (res.console_output || res.execution_time != null) {
        const summary = formatConsoleSummary({
          executionTime: res.execution_time,
          inputRows: res.input_rows,
          outputRows: res.output_rows,
        });
        setConsole({
          text: ['✓ 筛选完成', summary].filter(Boolean).join('\n\n'),
          type: 'success',
          consoleOutput: res.console_output || '',
        });
      }
      saveHistoryEntry(buildHistoryEntry({
        strategy: stratName,
        strategyId: loadedPresetId,
        start: formatSqlTime(startTime, false),
        end: formatSqlTime(endTime, true),
        startRaw: startTime,
        endRaw: endTime,
        count: data.length,
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
        result: res,
        summary,
        modeLabel: filterMode === 'rules' ? '规则' : filterMode === 'split' ? '对照' : '代码',
      }));
      toast(`查询完成 · ${data.length} 条`);
      if (res.task_id && data.length > 0) {
        try {
          const cfgRes = await api.getConfig();
          const cfg = cfgRes.config || {};
          if (cfg.viz_available) {
            const mode = cfg.viz_open_mode || 'prompt';
            if (mode === 'auto' && data.length <= 50) {
              await openSampleGalleryWhenReady(() => api.vizOpen({ source: 'query_task', task_id: res.task_id, dataset_name: summary }));
            } else if (mode === 'prompt') {
              toast('可点击结果栏「打开样本图库」在新窗口浏览与标注', 'info');
            }
          }
        } catch { /* 看图可选，失败不阻断查询 */ }
      }
    } catch (e) {
      toast(e.message, 'error');
      setConsole({ text: '✗ ' + e.message, type: 'error' });
    } finally { setLoading(false); }
  };
  onExecuteRef.current = onExecute;

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
      return;
    }
    const res = await api.getStrategy(id);
    if (!res.success) { toast(res.error, 'error'); return; }
    const s = res.data;
    setLoadedPresetId(id);
    originalFlowRef.current = s.flow ? JSON.parse(JSON.stringify(s.flow)) : null;
    localStorage.setItem('pc_last_preset', id);
    setSql(s.sql_template || DEFAULT_SQL);
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
    setSampleSize(sampleSettings.sampleSize);
    setRandomSeed(sampleSettings.randomSeed);
    prevSampleRef.current = { sampleSize: sampleSettings.sampleSize, randomSeed: sampleSettings.randomSeed };
    queueMicrotask(() => { skipSampleSyncRef.current = false; });
    setFilterMode(uiFilterMode(s.filter_mode || 'flow'));
    if (s.flow) studio.setFlow(s.flow);
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
    filter_mode: uiBackendMode,
    flow: resolvedFlow || { version: 2, nodes: [] },
    filter_rules_code: await studio.compile(),
  });

  const confirmSave = async () => {
    if (!saveName.trim()) { toast('请输入策略名称', 'error'); return; }
    try {
      const payload = await buildStrategyPayload(saveName.trim());
      const res = await api.saveStrategy(payload);
      if (!res.success) throw new Error(res.error);
      setSaveOpen(false);
      setLoadedPresetId(payload.id);
      originalFlowRef.current = payload.flow ? JSON.parse(JSON.stringify(payload.flow)) : null;
      localStorage.setItem('pc_last_preset', payload.id);
      await reloadStrategies();
      toast('策略已保存');
    } catch (e) { toast(e.message, 'error'); }
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
    setConsole({ text: '运行中…', type: 'run' });
    try {
      const parts = [];
      if (filterMode !== 'code') parts.push(await studio.compile());
      const sampleForRun = resolveSampleCodeForExecution(
        sampleCode,
        { sampleSize, randomSeed },
        hasInlineSampling(pythonCode, resolvedFlow, sampleCode),
      );
      if (sampleForRun) parts.push(sampleForRun);
      parts.push(pythonCode);
      const code = parts.filter(Boolean).join('\n\n');
      const res = await api.runPython({ python_code: code, task_id: taskId || undefined });
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
      setConsole({ text: e.message, type: 'error' }); }
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
        const recent = await fetchRecentPredictJobs();
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
        const recent = await fetchRecentPredictJobs();
        if (cancelled) return;
        setPredictJobs(recent);
        const jobId = await resolvePredictJobId({
          urlJobId: searchParams.get('predict_job'),
          sql: localStorage.getItem('pc_sql') || sql,
          recentJobs: recent,
        });
        if (!jobId) return;
        await applyPredictBatchSql(jobId, { silent: true });
      } catch { /* keep current SQL */ }
      finally {
        if (!cancelled) setPredictJobsLoading(false);
      }
    })();
    return () => { cancelled = true; };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const complexFlow = hasComplexFlow(originalFlowRef.current);

  const queryModeHint = (() => {
    const modeLabel = { rules: '规则筛选', code: 'Python 筛选', split: '规则 / 代码对照' }[filterMode];
    const prefix = loadedPresetId
      ? (strategies.find((s) => s.id === loadedPresetId)?.name || '策略')
      : '自由查询';
    return `${prefix} · SQL + ${modeLabel}`;
  })();

  const sampleSizeHint = inlineSample
    ? `代码内采样 ${sampleSize} 条 · 种子 ${randomSeed} · 参数在 apply_random_sample_rows 函数中`
    : filterMode !== 'code'
      ? `规则筛选后随机取 ${sampleSize} 条 · 种子 ${randomSeed} · 先预览再行数再执行`
      : `筛选后随机取 ${sampleSize} 条 · 种子 ${randomSeed} · 不足则全量`;

  return (
    <div className="panel active" id="panel-query">
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
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => { setSaveName(strategies.find((s) => s.id === loadedPresetId)?.name || ''); setSaveOpen(true); }}>保存</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={exportStrategy}>导出</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => importRef.current?.click()}>导入</button>
          <input ref={importRef} type="file" accept=".json" hidden onChange={(e) => { importStrategy(e.target.files?.[0]); e.target.value = ''; }} />
          {loadedPresetId && !String(loadedPresetId).startsWith('_') && (
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => setDeleteId(loadedPresetId)}>删除</button>
          )}
        </div>
        <div className="topbar-actions"><span className="kbd-hint">Ctrl + Enter 执行</span></div>
      </div>

      <div className="panel-scroll">
        <div className="section section-query">
          <div className="query-setup" id="query-setup">
          <div className="controls-card">
            <div className="control-inline control-source">
              <label htmlFor="data-source">数据源</label>
              <select id="data-source" value={dataSource} onChange={(e) => onChangeDataSource(e.target.value)}>
                <option value="predict_result">预测结果表</option>
                <option value="detail">检测明细表</option>
              </select>
            </div>
            {dataSource === 'predict_result' && (
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
                      #{j.id} · {j.name || 'predict'} · {j.done}/{j.total || '?'}
                    </option>
                  ))}
                </select>
                <span className="muted predict-job-hint">
                  {predictJobsLoading ? '匹配中…' : '自动匹配最近批次，可手动切换'}
                </span>
              </div>
            )}
            {dataSource !== 'predict_result' && (
            <>
            <div className="time-presets">
              {['today', 'yesterday', '7days', '30days'].map((p) => (
                <button key={p} type="button" className="preset-btn" onClick={() => { const r = setTimePreset(p); setStartTime(r.start); setEndTime(r.end); markStale(); }}>
                  {({ today: '今天', yesterday: '昨天', '7days': '近 7 天', '30days': '近 30 天' })[p]}
                </button>
              ))}
            </div>
            <div className="date-range">
              <input type="datetime-local" value={startTime} step={60} onChange={(e) => { setStartTime(e.target.value); markStale(); }} />
              <span className="date-sep">—</span>
              <input type="datetime-local" value={endTime} step={60} onChange={(e) => { setEndTime(e.target.value); markStale(); }} />
            </div>
            </>
            )}
            <div className="control-inline control-sample">
              <label htmlFor="sample-size">随机采样</label>
              <input id="sample-size" type="number" min={1} title="筛选后随机取 N 条" value={sampleSize} onChange={(e) => { setSampleSize(+e.target.value || DEFAULT_SAMPLE); markStale(); }} />
            </div>
            <div className="control-inline control-seed">
              <label htmlFor="random-seed">随机种子</label>
              <input id="random-seed" type="number" min={0} step={1} title="采样随机种子，相同种子可复现" value={randomSeed} onChange={(e) => { setRandomSeed(parseInt(e.target.value, 10) || 0); markStale(); }} />
            </div>
            <button type="button" className={`btn btn-secondary${previewStale ? ' is-recommended' : ''}`} disabled={previewLoading} onClick={onPreview}>{previewLoading ? '预览中…' : '预览筛选'}</button>
            <button type="button" className={`btn btn-primary${previewStale && studio.rules.length ? ' needs-preview' : ''}`} disabled={loading || previewLoading} onClick={onExecute}>{loading ? '执行中…' : '执行查询'}</button>
            {previewLoading && <div className="preview-progress" aria-hidden><div className="preview-progress-bar" /></div>}
          </div>

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
                  <div className="editor-pane-header">
                    <span className="ep-title">SQL 查询</span>
                    <div className="ep-header-right">
                      <span className="ep-hint">${'{START_TIME}'} · ${'{END_TIME}'}</span>
                      <button type="button" className="ep-btn ep-icon" title={editorWs.fullscreenPane === 'sql' ? '退出全屏' : '全屏编辑'} onClick={() => editorWs.toggleFullscreen('sql')}>
                        <FullscreenIcon />
                      </button>
                    </div>
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
                      {['rules', 'code', 'split'].map((m) => (
                        <button key={m} type="button" className={`filter-mode-tab${filterMode === m ? ' active' : ''}`} onClick={() => setFilterMode(m)}>
                          {({ rules: '规则', code: '代码', split: '对照' })[m]}
                        </button>
                      ))}
                    </div>
                    <div className="ep-header-right">
                      <div className="ep-actions">
                        <button type="button" className="ep-btn" onClick={() => setHelpOpen(true)}>帮助</button>
                        <button type="button" className="ep-btn" onClick={runPythonTest}>测试</button>
                        {(filterMode === 'code' || filterMode === 'split') && (
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
                    {filterMode === 'split' && (
                      <>
                        <div className="filter-panel filter-panel-rules is-split">
                          <RulesBuilder studio={studio} complexHint={complexFlow} keyboardActive={false} />
                        </div>
                        <div className="filter-panel filter-panel-split-code">
                          <div className="split-code-header">
                            <span>apply_filter_rules（自动生成）</span>
                            <button
                              type="button"
                              className="rules-code-copy"
                              onClick={() => {
                                navigator.clipboard?.writeText(studio.compiledCode || '');
                                toast('已复制规则代码');
                              }}
                            >
                              复制
                            </button>
                          </div>
                          <div className="editor-wrap">
                            <PythonEditor
                              value={studio.compiledCode || '# 添加规则后将自动生成 apply_filter_rules(df)'}
                              readOnly
                            />
                          </div>
                        </div>
                      </>
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
          </div>
        </div>
        <ConsolePanel visible={!!console} content={console} onClear={() => setConsole(null)} />
      </div>

      <ResultsPanel visible={rawResults.length > 0} rawData={rawResults} taskId={taskId} executionDetail={executionDetail} onArchive={() => toast('归档完成')} dataSource={dataSource} />

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
              await api.deleteStrategy(deleteId);
              setDeleteId('');
              loadStrategy('');
              reloadStrategies();
              toast('已删除');
            }}>删除</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
