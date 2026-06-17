const BASE = '';

import { formatSampleGalleryError } from '../lib/sampleGallery';
import { appNavigate } from '../lib/appNavigate';
import { appendViewerNavParams } from '../lib/viewerNav';

// 可选 API Token（后端配置 api_token 时启用）；存于 localStorage.pc_api_token
export function getApiToken() {
  try { return localStorage.getItem('pc_api_token') || ''; } catch { return ''; }
}
export function setApiToken(token) {
  try { token ? localStorage.setItem('pc_api_token', token) : localStorage.removeItem('pc_api_token'); } catch { /* ignore */ }
}

/** 为 <img src> 等无法带请求头的 URL 附加 ?token=（后端启用 api_token 时必需） */
export function appendApiToken(url) {
  const t = getApiToken();
  if (!t || !url) return url;
  const sep = url.includes('?') ? '&' : '?';
  return `${url}${sep}token=${encodeURIComponent(t)}`;
}

export function predictResultPreviewUrl(resultId) {
  return appendApiToken(`/api/forge/predict-result/${resultId}/preview`);
}
function authHeaders() {
  const t = getApiToken();
  return t ? { 'X-API-Token': t } : {};
}

function isNetworkFetchError(err) {
  const msg = String(err?.message || err || '');
  return (
    err?.name === 'TypeError'
    || /failed to fetch/i.test(msg)
    || /networkerror/i.test(msg)
    || /load failed/i.test(msg)
  );
}

function formatFetchError(err, path) {
  if (!isNetworkFetchError(err)) return err;
  const hint = '无法连接后端（http://127.0.0.1:5050）。若刚保存代码或重启过服务，请稍等几秒后重试。';
  const wrapped = new Error(`${hint}（${path}）`);
  wrapped.cause = err;
  wrapped.isNetwork = true;
  return wrapped;
}

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(options.headers || {}) },
      ...options,
    });
  } catch (err) {
    throw formatFetchError(err, path);
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok && data.success !== true) {
    const err = new Error(data.error || data.message || `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return data;
}

/**
 * SSE 流式 POST：解析 `data: {json}\n\n` 事件，逐条交给 onEvent 回调。
 * 与 request 共用 BASE / authHeaders / 网络错误提示，统一鉴权与错误处理。
 * @param {string} path
 * @param {object} [body]
 * @param {{ signal?: AbortSignal, onEvent?: (ev: any) => void, headers?: object }} [opts]
 */
async function streamRequest(path, body = {}, { signal, onEvent, headers } = {}) {
  let res;
  try {
    res = await fetch(`${BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders(), ...(headers || {}) },
      body: JSON.stringify(body),
      signal,
    });
  } catch (err) {
    throw formatFetchError(err, path);
  }
  if (!res.ok || !res.body) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.replace(/^data:\s?/, '').trim();
      if (!line) continue;
      let ev;
      try { ev = JSON.parse(line); } catch { continue; }
      onEvent?.(ev);
    }
  }
}

async function importPlatformModelsFallback(body = {}) {
  const approachId = body.approach_id;
  if (!approachId) throw new Error('缺少 approach_id');
  const includeDeploy = body.include_deploy !== false;
  const includeTrain = body.include_train !== false;
  const limit = body.limit || 100;
  const imported = [];
  const skipped = [];
  const failed = [];

  const importOne = async (payload, meta) => {
    try {
      const r = await request('/api/forge/models', { method: 'POST', body: JSON.stringify(payload) });
      imported.push({ ...meta, registry_id: r.id });
    } catch (e) {
      failed.push({ ...meta, error: e.message });
    }
  };

  if (includeDeploy) {
    const d = await request(`/api/deployed-models?approach_id=${approachId}&limit=${limit}`);
    for (const m of d.models || []) {
      const meta = { source: 'modeldeploy', id: m.id, name: m.deploy_name };
      if (!m.path_resolvable || !m.full_path) {
        skipped.push({ ...meta, reason: '路径不可用' });
        continue;
      }
      await importOne({
        name: m.deploy_name,
        checkpoint_path: m.full_path,
        model_type: m.model_type,
        labels: m.labels,
        source: 'modeldeploy',
        source_ref: String(m.id),
        approach_id: m.approach_id || approachId,
      }, meta);
    }
  }

  if (includeTrain) {
    const t = await request(`/api/training-models?approach_id=${approachId}&limit=${limit}`);
    for (const m of t.models || []) {
      const meta = { source: 'modeltrainconfig', id: m.id, name: m.model_name };
      const path = m.full_path || m.hint_path;
      if (!m.path_resolvable || !path) {
        skipped.push({ ...meta, reason: '权重文件不存在' });
        continue;
      }
      await importOne({
        name: m.model_name,
        checkpoint_path: path,
        model_type: m.model_type,
        labels: m.labels,
        source: 'modeltrainconfig',
        source_ref: String(m.id),
        approach_id: m.approach_id || approachId,
      }, meta);
    }
  }

  return {
    success: true,
    imported,
    skipped,
    failed,
    imported_count: imported.length,
    skipped_count: skipped.length,
    failed_count: failed.length,
    fallback: true,
  };
}

export const api = {
  getConfig: () => request('/api/config'),
  listInterruptedJobs: () => request('/api/lifecycle/interrupted-jobs'),
  resolveInterruptedJobs: (body) => request('/api/lifecycle/interrupted-jobs', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  getUserGuide: () => request('/api/docs/user-guide'),
  saveConfig: (config) => request('/api/config', { method: 'POST', body: JSON.stringify({ config }) }),
  testConnection: (body) => request('/api/config/test-connection', { method: 'POST', body: JSON.stringify(body) }),
  testMagicFoxConnection: (body) => request('/api/config/test-magic-fox', { method: 'POST', body: JSON.stringify(body || {}) }),

  query: (body) => request('/api/query', { method: 'POST', body: JSON.stringify(body) }),
  submitQueryJob: (body) => request('/api/query/jobs', { method: 'POST', body: JSON.stringify(body) }),
  listQueryJobs: (params = {}) => {
    const q = new URLSearchParams();
    if (params.limit) q.set('limit', String(params.limit));
    if (params.active_only) q.set('active_only', '1');
    const qs = q.toString();
    return request(`/api/query/jobs${qs ? `?${qs}` : ''}`);
  },
  getQueryJob: (jobId) => request(`/api/query/jobs/${encodeURIComponent(jobId)}`),
  queryTask: (taskId) => request(`/api/query/task/${encodeURIComponent(taskId)}`),
  previewFilter: (body) => request('/api/preview-filter', { method: 'POST', body: JSON.stringify(body) }),
  runPython: (body) => request('/api/run-python-code', { method: 'POST', body: JSON.stringify(body) }),

  getStrategies: () => request('/api/strategies'),
  getStrategy: (id) => request(`/api/strategies/${id}`),
  getStrategyVariables: (id) => request(`/api/strategies/${id}/variables`),
  getPythonPresets: () => request('/api/python-presets'),
  getPipelineTemplates: () => request('/api/pipeline-templates'),
  compileProcessPipeline: (body) => request('/api/strategies/compile-pipeline', { method: 'POST', body: JSON.stringify(body) }),

  listEnvProfiles: () => request('/api/env-profiles'),
  getEnvProfile: (id) => request(`/api/env-profiles/${encodeURIComponent(id)}`),
  saveEnvProfile: (body) => request('/api/env-profiles', { method: 'POST', body: JSON.stringify(body) }),
  deleteEnvProfile: (id) => request(`/api/env-profiles/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  suggestEnvProfileVars: (body) => request('/api/env-profiles/suggest', { method: 'POST', body: JSON.stringify(body) }),
  saveStrategy: (body) => request('/api/strategies', { method: 'POST', body: JSON.stringify(body) }),
  deleteStrategy: (id) => request(`/api/strategies/${id}`, { method: 'DELETE' }),
  executeStrategy: (body) => request('/api/strategies/execute', { method: 'POST', body: JSON.stringify(body) }),

  getTemplates: () => request('/api/templates'),
  saveTemplate: (body) => request('/api/templates', { method: 'POST', body: JSON.stringify(body) }),
  deleteTemplate: (id) => request(`/api/templates/${id}`, { method: 'DELETE' }),

  getFlowNodes: () => request('/api/flow/nodes'),
  compileFlow: (body) => request('/api/flow/compile', { method: 'POST', body: JSON.stringify(body) }),

  getPipelines: (limit = 50) => request(`/api/pipelines?limit=${limit}`),
  getPipelineNodes: (id) => request(`/api/pipelines/${id}/nodes`),
  getPipelineRules: (id, params = '') => request(`/api/pipelines/${id}/filter-rules${params}`),

  getDefectCategories: (refresh = false, approachId) => {
    const q = new URLSearchParams();
    if (refresh) q.set('refresh', '1');
    if (approachId != null) q.set('approach_id', String(approachId));
    const qs = q.toString();
    return request(`/api/defect-categories${qs ? `?${qs}` : ''}`);
  },
  getPlatformPaths: (drive) => request(`/api/platform-paths${drive ? `?drive=${encodeURIComponent(drive)}` : ''}`),
  syncPlatformPaths: (body) => request('/api/platform-paths/sync', { method: 'POST', body: JSON.stringify(body || {}) }),

  getDeployedModels: (params = '') => request(`/api/deployed-models${params}`),
  getTrainingModels: (params = '') => request(`/api/training-models${params}`),

  // ── 写库 detforge：模型注册 / 作业 / 人工质检 ──
  forgeSchemaStatus: () => request('/api/forge/schema/status'),
  forgeSchemaInit: () => request('/api/forge/schema/init', { method: 'POST' }),

  forgeModels: (enabledOnly = false) => request(`/api/forge/models${enabledOnly ? '?enabled=1' : ''}`),
  forgeCreateModel: (body) => request('/api/forge/models', { method: 'POST', body: JSON.stringify(body) }),
  forgeDeleteModel: (id) => request(`/api/forge/models/${id}`, { method: 'DELETE' }),
  forgeSetModelEnabled: (id, enabled) => request(`/api/forge/models/${id}/enabled`, { method: 'POST', body: JSON.stringify({ enabled }) }),

  forgeJobs: (params = '') => request(`/api/forge/jobs${params}`),
  forgeJob: (id) => request(`/api/forge/jobs/${id}`),
  forgeJobLog: (id, { limit = 0 } = {}) => {
    const q = limit > 0 ? `?limit=${limit}` : '?limit=0';
    return request(`/api/forge/jobs/${id}/log${q}`);
  },
  forgeExportDownloadUrl: (relPath) => {
    const t = getApiToken();
    const q = new URLSearchParams({ path: relPath });
    if (t) q.set('token', t);
    return `/api/forge/exports/download?${q.toString()}`;
  },
  forgeEnqueuePredict: (body) => request('/api/forge/jobs/predict', { method: 'POST', body: JSON.stringify(body) }),
  // 批量预测与单模型共用 /predict（旧服务无 /predict/batch 时也能工作）
  forgeEnqueuePredictBatch: (body) => request('/api/forge/jobs/predict', { method: 'POST', body: JSON.stringify(body) }),
  forgeImportAllPlatformModels: async (body) => {
    try {
      return await request('/api/forge/platform/models/import-all', { method: 'POST', body: JSON.stringify(body) });
    } catch (e) {
      if (e.status !== 404) throw e;
      return importPlatformModelsFallback(body);
    }
  },
  forgeControlJob: (id, action) => request(`/api/forge/jobs/${id}/control`, { method: 'POST', body: JSON.stringify({ action }) }),
  forgeJobItems: (id, params = '') => request(`/api/forge/jobs/${id}/items${params}`),
  forgeJobResults: (id, params = '') => request(`/api/forge/jobs/${id}/results${params}`),
  forgeJobOpenViz: (id, body = {}) => request(`/api/forge/jobs/${id}/viz`, { method: 'POST', body: JSON.stringify(body) }),
  forgePredictResultPreviewUrl: (id) => predictResultPreviewUrl(id),
  forgeModelHealth: (id, device) => request(`/api/forge/models/${id}/health`, { method: 'POST', body: JSON.stringify(device ? { device } : {}) }),
  forgePredictResultSource: () => request('/api/forge/predict-result/source'),

  forgeManualQcLookup: (sn, limit = 50) => request(
    `/api/forge/manual-qc/lookup?sn=${encodeURIComponent(sn)}&limit=${limit}`,
  ),
  forgeManualQcVizOpen: (body) => request('/api/forge/manual-qc/viz-open', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcQueue: (params = '') => request(`/api/forge/manual-qc/queue${params}`),
  forgeManualQcIntake: (body) => request('/api/forge/manual-qc/intake', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcReview: (id, body) => request(`/api/forge/manual-qc/review/${id}`, { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcConfirm: (body) => request('/api/forge/manual-qc/confirm', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcVoid: (ids, reason) => request('/api/forge/manual-qc/void', {
    method: 'POST', body: JSON.stringify({ ids, reason }),
  }),
  forgeManualQcList: (params = '') => request(`/api/forge/manual-qc${params}`),
  forgeManualQcGet: (id) => request(`/api/forge/manual-qc/${id}`),
  forgeManualQcHistory: (id, params = '') => request(`/api/forge/manual-qc/${id}/history${params}`),
  forgeManualQcRevise: (id, body) => request(`/api/forge/manual-qc/${id}/revise`, { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcSummary: () => request('/api/forge/manual-qc/summary'),
  forgeManualQcBatches: (params = '') => request(`/api/forge/manual-qc/batches${params}`),
  forgeManualQcArchive: (body) => request('/api/forge/manual-qc', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcCategories: () => request('/api/forge/manual-qc/categories'),
  forgeManualQcSaveCategories: (body) => request('/api/forge/manual-qc/categories', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcArchiveSettings: () => request('/api/forge/manual-qc/archive-settings'),
  forgeManualQcSaveArchiveSettings: (body) => request('/api/forge/manual-qc/archive-settings', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcArchiveSync: (body) => request('/api/forge/manual-qc/archive-sync', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcExport: (body) => request('/api/forge/manual-qc/export', { method: 'POST', body: JSON.stringify(body) }),
  forgeManualQcUpdate: (id, body) => request(`/api/forge/manual-qc/${id}`, { method: 'PATCH', body: JSON.stringify(body) }),
  forgeManualQcDelete: (id) => request(`/api/forge/manual-qc/${id}`, { method: 'DELETE' }),
  forgeManualQcCleanupUploads: (dryRun = true) => request('/api/forge/manual-qc/cleanup-uploads', { method: 'POST', body: JSON.stringify({ dry_run: dryRun }) }),
  forgeManualQcExportZip: async (body) => {
    const res = await fetch('/api/forge/manual-qc/export', {
      method: 'POST', headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ ...body, as_zip: true }),
    });
    if (!res.ok) { const d = await res.json().catch(() => ({})); throw new Error(d.error || `HTTP ${res.status}`); }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    const cd = res.headers.get('Content-Disposition') || '';
    a.href = url; a.download = (cd.match(/filename="?([^"]+)"?/) || [])[1] || 'manual_qc_export.zip';
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  },
  forgeManualQcUpload: async (fileList) => {
    const fd = new FormData();
    Array.from(fileList || []).forEach((f) => fd.append('files', f));
    const res = await fetch('/api/forge/manual-qc/upload', { method: 'POST', body: fd, headers: { ...authHeaders() } });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && data.success !== true) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },

  forgeCurationList: (params = '') => request(`/api/forge/curation${params}`),
  forgeCurationCreate: (body) => request('/api/forge/curation', { method: 'POST', body: JSON.stringify(body) }),
  forgeCurationGet: (id) => request(`/api/forge/curation/${id}`),
  forgeCurationDelete: (id) => request(`/api/forge/curation/${id}`, { method: 'DELETE' }),
  forgeCurationItems: (id, params = '') => request(`/api/forge/curation/${id}/items${params}`),
  forgeCurationExport: (id, body = {}) => request(`/api/forge/curation/${id}/export`, { method: 'POST', body: JSON.stringify(body) }),
  forgeCurationArchive: (id, body = {}) => request(`/api/forge/curation/${id}/archive`, { method: 'POST', body: JSON.stringify(body) }),
  forgeCurationHandoff: (id, body = {}) => request(`/api/forge/curation/${id}/handoff`, { method: 'POST', body: JSON.stringify(body) }),
  forgeCurationHandoffDone: (id, body = {}) => request(`/api/forge/curation/${id}/handoff-done`, { method: 'POST', body: JSON.stringify(body) }),
  forgeCurationDownloadUrl: (id) => {
    const t = getApiToken();
    return `/api/forge/curation/${id}/download${t ? `?token=${encodeURIComponent(t)}` : ''}`;
  },
  forgeCurationImport: async (id, file) => {
    const fd = new FormData();
    fd.append('file', file);
    const res = await fetch(`/api/forge/curation/${id}/import`, {
      method: 'POST',
      headers: { ...authHeaders() },
      body: fd,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok && data.success !== true) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  },
  forgeArchiveHandoffList: (params = '') => request(`/api/forge/archive-handoff${params}`),
  forgeManualQcHandoff: (body) => request('/api/forge/manual-qc/handoff', { method: 'POST', body: JSON.stringify(body) }),
  forgeReplayEvalPreview: (body) => request('/api/forge/replay-eval/preview', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  forgeReplayEvalCreate: (body) => request('/api/forge/replay-eval/create', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  forgeReplayRunPreview: (body) => request('/api/forge/replay-runs/preview', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  forgeReplayRunVariables: (body) => request('/api/forge/replay-runs/variables', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  forgeReplayRunCreate: (body) => request('/api/forge/replay-runs', {
    method: 'POST',
    body: JSON.stringify(body),
  }),
  forgeReplayRunGet: (id) => request(`/api/forge/replay-runs/${id}`),
  forgeReplayRunList: (params = '') => request(`/api/forge/replay-runs${params}`),

  forgeWorkflowTemplates: () => request('/api/forge/workflows/templates'),
  forgeWorkflowTemplate: (id) => request(`/api/forge/workflows/templates/${encodeURIComponent(id)}`),
  forgeComposeFlows: () => request('/api/forge/workflows/compose-flows'),
  forgeComposeFlowGet: (id) => request(`/api/forge/workflows/compose-flows/${encodeURIComponent(id)}`),
  forgeComposeFlowSave: (body) => request('/api/forge/workflows/compose-flows', { method: 'POST', body: JSON.stringify(body) }),
  forgeRunEnvTemplates: (params = '') => request(`/api/forge/workflows/run-env-templates${params}`),
  forgeRunEnvPreview: (body) => request('/api/forge/workflows/run-env/preview', { method: 'POST', body: JSON.stringify(body) }),
  forgeComposeFlowScheduleGet: (id) => request(`/api/forge/workflows/compose-flows/${encodeURIComponent(id)}/schedule`),
  forgeComposeFlowScheduleSave: (id, body) => request(
    `/api/forge/workflows/compose-flows/${encodeURIComponent(id)}/schedule`,
    { method: 'PUT', body: JSON.stringify(body) },
  ),
  forgeWorkflowRuns: (params = '') => request(`/api/forge/workflows/runs${params}`),
  forgeWorkflowRunCreate: (body) => request('/api/forge/workflows/runs', { method: 'POST', body: JSON.stringify(body) }),
  forgeWorkflowRun: (id) => request(`/api/forge/workflows/runs/${id}`),
  forgeWorkflowRunResume: (id) => request(`/api/forge/workflows/runs/${id}/resume`, { method: 'POST' }),
  forgeWorkflowSchedules: (params = '') => request(`/api/forge/workflows/schedules${params}`),
  forgeWorkflowScheduleCreate: (body) => request('/api/forge/workflows/schedules', { method: 'POST', body: JSON.stringify(body) }),
  forgeWorkflowScheduleUpdate: (id, body) => request(`/api/forge/workflows/schedules/${id}`, {
    method: 'PATCH', body: JSON.stringify(body),
  }),
  forgeWorkflowScheduleTrigger: (id) => request(`/api/forge/workflows/schedules/${id}/trigger`, { method: 'POST' }),
  forgeWorkflowNotifications: (params = '') => request(`/api/forge/workflows/notifications${params}`),

  listTools: () => request('/api/tools'),
  toolStats: () => request('/api/tools/stats'),
  executeTool: (toolId, body) => request(`/api/tools/${encodeURIComponent(toolId)}/execute`, {
    method: 'POST', body: JSON.stringify(body),
  }),
  catalogSync: (body = {}) => request('/api/catalog/sync', { method: 'POST', body: JSON.stringify(body) }),
  catalogLogs: (params = '?limit=20') => request(`/api/catalog/logs${params}`),
  listPipelines: () => request('/api/pipelines'),
  workflowAgentCompile: (body) => request('/api/workflows/agent-compile', { method: 'POST', body: JSON.stringify(body) }),
  workflowImport: (body) => request('/api/workflows/import', { method: 'POST', body: JSON.stringify(body) }),

  flowDemoInfo: () => request('/api/flows/demo'),
  flowRun: (body) => request('/api/flows/run', { method: 'POST', body: JSON.stringify(body) }),
  flowList: () => request('/api/flows/list'),
  flowReleases: () => request('/api/flows/releases'),
  flowRunsList: (params = '') => request(`/api/flows/runs${params}`),
  flowRunGet: (runKey) => request(`/api/flows/runs/${encodeURIComponent(runKey)}`),
  flowRunResume: (runKey, body = {}) => request(`/api/flows/runs/${encodeURIComponent(runKey)}/resume`, {
    method: 'POST', body: JSON.stringify(body),
  }),
  flowPipelineYaml: (flowId) => request(`/api/flows/pipelines/${encodeURIComponent(flowId)}/yaml`),
  flowPipelineGraph: (flowId) => request(`/api/flows/pipelines/${encodeURIComponent(flowId)}/graph`),
  flowAgentContext: (params = '') => request(`/api/flows/agent/context${params}`),
  flowAgentCompose: (body) => request('/api/flows/agent/compose', { method: 'POST', body: JSON.stringify(body) }),
  flowAgentComposeStream: (body, opts) => streamRequest('/api/flows/agent/compose/stream', body, opts),
  flowAgentValidate: (body) => request('/api/flows/agent/validate', { method: 'POST', body: JSON.stringify(body) }),
  flowAgentPreviewGraph: (body) => request('/api/flows/agent/preview-graph', { method: 'POST', body: JSON.stringify(body) }),
  flowAgentSave: (body) => request('/api/flows/agent/save', { method: 'POST', body: JSON.stringify(body) }),

  workbenchTodos: (params = '') => request(`/api/workbench/todos${params}`),
  workbenchSummary: () => request('/api/workbench/summary'),
  workbenchFlowRuns: (params = '') => request(`/api/workbench/flows/runs${params}`),
  workbenchFlowList: () => request('/api/workbench/flows/list'),

  orchestrationResume: (body) => request('/v1/orchestration/resume', {
    method: 'POST', body: JSON.stringify(body),
  }),
  orchestrationPaused: (params = '') => request(`/v1/orchestration/executions/paused${params}`),

  forgeSyncTestAuth: () => request('/api/forge/sync/test-auth', { method: 'POST' }),
  forgeSyncDiscover: (body) => request('/api/forge/sync/discover', { method: 'POST', body: JSON.stringify(body) }),
  forgeSyncDiscoverImport: (body) => request('/api/forge/sync/discover/import', { method: 'POST', body: JSON.stringify(body) }),
  forgeSyncProjects: () => request('/api/forge/sync/projects'),
  forgeSyncSaveProject: (body) => request('/api/forge/sync/projects', { method: 'POST', body: JSON.stringify(body) }),
  forgeSyncDeleteProject: (id) => request(`/api/forge/sync/projects/${id}`, { method: 'DELETE' }),
  forgeSyncDatasets: (params = '') => request(`/api/forge/sync/datasets${params}`),
  forgeSyncSaveDataset: (body) => request('/api/forge/sync/datasets', { method: 'POST', body: JSON.stringify(body) }),
  forgeSyncDeleteDataset: (id) => request(`/api/forge/sync/datasets/${id}`, { method: 'DELETE' }),
  forgeSyncDatasetStatus: (id) => request(`/api/forge/sync/datasets/${id}/status`),
  forgeSyncRun: (id, body = {}) => request(`/api/forge/sync/datasets/${id}/run`, { method: 'POST', body: JSON.stringify(body) }),
  forgeSyncOpenViz: (id) => request(`/api/forge/sync/datasets/${id}/viz`, { method: 'POST' }),
  forgeSyncDatasetItems: (id, params = '') => request(`/api/forge/sync/datasets/${id}/items${params}`),
  forgeSyncDatasetRetrace: (id) => request(`/api/forge/sync/datasets/${id}/retrace`, { method: 'POST' }),
  forgeSyncTrainModels: (projectId, force = false) => request('/api/forge/sync/train-models', {
    method: 'POST',
    body: JSON.stringify({ project_id: projectId, force }),
  }),
  forgeListTrainModels: (projectId) => request(`/api/forge/sync/train-models?project_id=${projectId}`),

  imageUrl: (name, path) => {
    const t = getApiToken();
    return `/api/image/${encodeURIComponent(name)}?path=${encodeURIComponent(path || '')}${t ? `&token=${encodeURIComponent(t)}` : ''}`;
  },
  exportCocoUrl: (taskId) => `/api/export/${taskId}`,
  exportCsvUrl: (taskId) => `/api/export-csv/${taskId}`,
  archive: (taskId, body) => request(`/api/archive/${taskId}`, { method: 'POST', body: JSON.stringify(body) }),
  getArchiveJob: (jobId) => request(`/api/archive/jobs/${encodeURIComponent(jobId)}`),

  vizStatus: () => request('/api/viz/status'),
  vizOpen: (body) => request('/api/viz/open', { method: 'POST', body: JSON.stringify(body) }),
  vizSession: (sessionId) => request(`/api/viz/session/${encodeURIComponent(sessionId)}`),
};

/** 样本图库页内路由（/viewer） */
export function sampleGalleryViewerPath(record) {
  if (typeof record === 'string') {
    if (record.startsWith('/viewer')) return record;
    return `/viewer?src=${encodeURIComponent(record)}`;
  }
  const vizUrl = record?.viz_url
    || (record?.session_id ? `/viz/?defectloop_session=${record.session_id}` : null);
  if (vizUrl) return `/viewer?src=${encodeURIComponent(vizUrl)}`;
  if (record?.viewer_url?.startsWith('/viewer')) return record.viewer_url;
  return '/viewer';
}

/** 在应用内或新窗口打开样本图库 */
export function openSampleGallery(record, options = {}) {
  const { newWindow = false, taskId, returnTo } = options;
  const path = appendViewerNavParams(sampleGalleryViewerPath(record), { taskId, returnTo });
  if (newWindow) {
    window.open(path, '_blank', 'noopener,noreferrer');
    return;
  }
  if (!appNavigate(path)) {
    window.location.assign(path);
  }
}

const VIZ_OPEN_BODY_KEY = 'pc_viz_open_body';

/** 先进入 /viewer 再在页内准备（避免长时间卡在查询页）。 */
export function openSampleGalleryDeferred(openBody, options = {}) {
  const { taskId, returnTo, newWindow } = options;
  if (!openBody?.task_id && !openBody?.source) {
    throw new Error('openBody 缺少 task_id');
  }
  if (newWindow) return null;
  try {
    sessionStorage.setItem(VIZ_OPEN_BODY_KEY, JSON.stringify(openBody));
  } catch {
    return null;
  }
  const prepPath = appendViewerNavParams('/viewer?preparing=1', { taskId: taskId || openBody.task_id, returnTo });
  if (!appNavigate(prepPath)) window.location.assign(prepPath);
  return { deferred: true };
}

/** 准备样本图库会话后直接跳转看图页（默认 task 查询走 deferred 快速路径）。 */
export async function openSampleGalleryWhenReady(prepare, context = '', options = {}) {
  const status = await api.vizStatus().catch(() => ({ available: false }));
  if (status && status.available === false) {
    throw new Error(formatSampleGalleryError('样本图库不可用', context));
  }
  const { taskId, returnTo, newWindow, openBody, defer = true } = options;

  if (defer && !newWindow && (openBody || taskId)) {
    let body = openBody;
    if (!body && taskId) {
      body = { source: 'query_task', task_id: taskId };
    }
    if (body && openSampleGalleryDeferred(body, { taskId, returnTo, newWindow })) {
      return { deferred: true };
    }
  }

  try {
    let body = openBody;
    if (!body && taskId) {
      body = { source: 'query_task', task_id: taskId };
    }
    const record = typeof prepare === 'function'
      ? await prepare()
      : await api.vizOpen(body);
    if (!record?.success && record?.error) {
      throw new Error(record.error);
    }
    openSampleGallery(record, options);
    return { record };
  } catch (err) {
    throw new Error(formatSampleGalleryError(err, context));
  }
}

export { VIZ_OPEN_BODY_KEY };

export function formatSqlTime(dtLocal, end = false) {
  if (!dtLocal) return '';
  const s = dtLocal.replace('T', ' ');
  return end && s.length === 16 ? `${s}:59` : s.length === 16 ? `${s}:00` : s;
}

export function toast(msg, type = 'info') {
  window.dispatchEvent(new CustomEvent('pc-toast', { detail: { msg, type } }));
}
