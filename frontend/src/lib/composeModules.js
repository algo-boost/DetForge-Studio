/**
 * 组合编排模块注册表：每个业务步骤 = 可复用组件（schema + 默认 + 上游绑定）。
 * 与 studio/forge/workflow_steps.py STEP_HANDLERS 对齐。
 */

function defaultParamsFromSchema(schema) {
  const out = {};
  for (const [key, spec] of Object.entries(schema || {})) {
    if (spec?.default != null) {
      out[key] = spec.default;
    } else if (spec?.type === 'time_window') {
      out[key] = { preset: 'yesterday' };
    } else if (spec?.type === 'strategy') {
      out[key] = '';
    } else if (spec?.type === 'boolean') {
      out[key] = false;
    }
  }
  return out;
}

export const COMPOSE_MODULE_GROUPS = [
  { id: 'data', label: '数据' },
  { id: 'predict', label: '预测' },
  { id: 'curation', label: '筛选归档' },
  { id: 'human', label: '人工' },
  { id: 'system', label: '系统' },
];

/** @typedef {{ fromKind: string, field: string, label?: string }} ComposeBindRule */

export const COMPOSE_MODULES = {
  query: {
    moduleId: 'query',
    kind: 'query',
    label: '数据查询',
    group: 'data',
    paramsSchema: {
      strategy_id: { type: 'strategy', required: true, label: '策略' },
      time_window: { type: 'time_window', label: '时间窗' },
    },
    defaults: { data_source: 'detail' },
    bindRules: {},
  },
  query_predict: {
    moduleId: 'query_predict',
    kind: 'query',
    label: '预测结果查询',
    group: 'data',
    paramsSchema: {
      strategy_id: { type: 'strategy', required: true, label: '策略' },
      time_window: { type: 'time_window', label: '时间窗' },
    },
    defaults: { data_source: 'predict_result' },
    bindRules: {
      predict_job_id: { fromKind: 'predict', field: 'job_id', label: '预测任务' },
    },
  },
  predict: {
    moduleId: 'predict',
    kind: 'predict',
    label: '批量预测',
    group: 'predict',
    paramsSchema: {
      model_id: { type: 'model', required: true, label: '模型' },
      threshold: { type: 'number', default: 0.1, label: '置信度阈值' },
      device: { type: 'string', default: '', label: '推理设备' },
      max_size: { type: 'number', default: 1536, label: '输入尺寸' },
    },
    defaults: {},
    bindRules: {
      task_id: { fromKind: 'query', field: 'task_id', label: '查询任务' },
    },
  },
  curation_create: {
    moduleId: 'curation_create',
    kind: 'curation_create',
    label: '创建筛选批次',
    group: 'curation',
    paramsSchema: {
      strategy_id: { type: 'strategy', label: '策略（可选）' },
      reviewer: { type: 'string', label: '复核人' },
      intent_type: { type: 'string', default: 'replay_eval', label: '意图类型' },
    },
    defaults: { data_source: 'predict_result', intent_type: 'replay_eval' },
    bindRules: {
      task_id: { fromKind: 'query', field: 'task_id', label: '查询任务' },
    },
  },
  curation_export: {
    moduleId: 'curation_export',
    kind: 'curation_export',
    label: '导出 COCO 出站',
    group: 'curation',
    paramsSchema: {
      include_images: { type: 'boolean', default: true, label: '包含图片' },
    },
    defaults: { include_images: true },
    bindRules: {
      batch_id: { fromKind: 'curation_create', field: 'batch_id', label: '筛选批次' },
    },
  },
  gate_human: {
    moduleId: 'gate_human',
    kind: 'gate_human',
    label: '人工卡点',
    group: 'human',
    paramsSchema: {
      instructions: { type: 'string', label: '说明' },
    },
    defaults: {
      gate_type: 'curation_coco_edit',
      instructions: '请编辑出站 COCO 并上传后继续',
    },
    bindRules: {
      batch_id: { fromKind: 'curation_create', field: 'batch_id', label: '筛选批次' },
    },
  },
  curation_import: {
    moduleId: 'curation_import',
    kind: 'curation_import',
    label: '导入 COCO',
    group: 'curation',
    paramsSchema: {},
    defaults: {},
    bindRules: {
      batch_id: { fromKind: 'curation_create', field: 'batch_id', label: '筛选批次' },
    },
  },
  curation_archive: {
    moduleId: 'curation_archive',
    kind: 'curation_archive',
    label: '筛选归档',
    group: 'curation',
    paramsSchema: {
      copy_images: { type: 'boolean', default: true, label: '复制图片' },
    },
    defaults: { copy_images: true },
    bindRules: {
      batch_id: { fromKind: 'curation_create', field: 'batch_id', label: '筛选批次' },
    },
  },
  notify: {
    moduleId: 'notify',
    kind: 'notify',
    label: '流程通知',
    group: 'system',
    paramsSchema: {
      event: { type: 'string', default: 'workflow_done', label: '事件' },
    },
    defaults: { event: 'workflow_done' },
    bindRules: {},
  },
};

export const RUN_TIME_WINDOW_PRESETS = [
  { id: 'yesterday', label: '昨日' },
  { id: 'today', label: '当日' },
  { id: 'last_7d', label: '近 7 天' },
];

/** 组合编排定时 preset → cron 五段表达式 */
export const COMPOSE_CRON_PRESETS = [
  { id: 'daily_02', label: '每天 02:00', cron: '0 2 * * *' },
  { id: 'daily_06', label: '每天 06:00', cron: '0 6 * * *' },
  { id: 'weekly_mon_08', label: '每周一 08:00', cron: '0 8 * * 1' },
  { id: 'hourly', label: '每小时整点', cron: '0 * * * *' },
  { id: 'custom', label: '自定义…', cron: '' },
];

export function cronPresetFromExpr(cronExpr) {
  const expr = String(cronExpr || '').trim();
  const hit = COMPOSE_CRON_PRESETS.find((p) => p.cron && p.cron === expr);
  return hit ? hit.id : 'custom';
}

export const DEFAULT_FLOW_ID = 'flow_draft';

export function normalizeFlowId(raw) {
  let slug = String(raw || '').trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '_').replace(/^_+|_+$/g, '');
  if (!slug) slug = `draft_${Date.now()}`;
  if (!slug.startsWith('flow_')) slug = `flow_${slug}`;
  return slug.slice(0, 128);
}

export function encodeStepId(flowId, seq) {
  return `${normalizeFlowId(flowId)}.s${String(seq).padStart(2, '0')}`;
}

export function isComposeFlowId(flowId) {
  const fid = String(flowId || '');
  return fid.startsWith('flow_') || fid.startsWith('custom_');
}

function stripUiParams(params) {
  if (!params || typeof params !== 'object') return params;
  return Object.fromEntries(Object.entries(params).filter(([k]) => !String(k).startsWith('_')));
}

export function reindexComposeSteps(flowId, steps) {
  const fid = normalizeFlowId(flowId);
  return (steps || []).map((s, i) => ({
    ...s,
    uid: encodeStepId(fid, i + 1),
  }));
}

export const DEFAULT_MODULE_IDS = ['query', 'predict'];

export const DEFAULT_COMPOSE_PIPELINE = DEFAULT_MODULE_IDS.map((moduleId, i) => ({
  uid: encodeStepId(DEFAULT_FLOW_ID, i + 1),
  moduleId,
}));

/** @deprecated 使用 DEFAULT_COMPOSE_PIPELINE */
export const MVP_COMPOSE_STEP_IDS = ['query', 'predict'];

export function getComposeModule(moduleId) {
  return COMPOSE_MODULES[moduleId] || null;
}

export function modulesForGroup(groupId) {
  return Object.values(COMPOSE_MODULES).filter((m) => m.group === groupId);
}

export function defaultParamsForModule(moduleId) {
  const mod = getComposeModule(moduleId);
  if (!mod) return {};
  return {
    ...(mod.defaults || {}),
    ...defaultParamsFromSchema(mod.paramsSchema),
  };
}

/** @deprecated 使用 defaultParamsForModule */
export function defaultComposeStepParams(moduleId) {
  return defaultParamsForModule(moduleId);
}

export function newComposeStep(moduleId, existingSteps = [], flowId = DEFAULT_FLOW_ID) {
  const mod = getComposeModule(moduleId);
  if (!mod) throw new Error(`未知模块: ${moduleId}`);
  const seq = (existingSteps?.length || 0) + 1;
  return {
    uid: encodeStepId(flowId, seq),
    moduleId,
    params: defaultParamsForModule(moduleId),
  };
}

export function defaultComposePipelineState(flowId = DEFAULT_FLOW_ID) {
  return reindexComposeSteps(
    flowId,
    DEFAULT_MODULE_IDS.map((moduleId) => ({
      moduleId,
      params: defaultParamsForModule(moduleId),
    })),
  );
}

function findUpstreamStep(builtSteps, fromKind) {
  for (let i = builtSteps.length - 1; i >= 0; i -= 1) {
    if (builtSteps[i].kind === fromKind) return builtSteps[i];
  }
  return null;
}

function bindHintsForModule(moduleId, builtSteps) {
  const mod = getComposeModule(moduleId);
  if (!mod?.bindRules) return [];
  return Object.entries(mod.bindRules).map(([param, rule]) => {
    const upstream = findUpstreamStep(builtSteps, rule.fromKind);
    const ok = Boolean(upstream);
    const upstreamLabel = upstream?.label || upstream?.id || rule.fromKind;
    const fieldLabel = rule.label || rule.field;
    return {
      param,
      label: fieldLabel,
      ok,
      upstreamId: upstream?.id,
      upstreamLabel,
      upstreamField: rule.field,
      detail: ok
        ? `步骤「${upstreamLabel}」· 输出 ${rule.field}`
        : undefined,
      text: ok
        ? `${fieldLabel} 将在运行时自动取自上游「${upstreamLabel}」的 ${rule.field}，无需手动填写`
        : `需要在上游添加 ${rule.fromKind} 类型步骤（当前缺失，无法自动接入 ${fieldLabel}）`,
    };
  });
}

/**
 * @param {Array<{ uid: string, moduleId: string, params?: object }>} stepInstances
 * @param {{ flowId?: string, useRunTimeWindow?: boolean }} options
 */
export function buildComposeDefinition(stepInstances, options = {}) {
  const flowId = normalizeFlowId(options.flowId || DEFAULT_FLOW_ID);
  const useRunTimeWindow = options.useRunTimeWindow !== false;
  const instances = reindexComposeSteps(flowId, stepInstances || []);
  const steps = [];
  const built = [];

  for (let i = 0; i < instances.length; i += 1) {
    const inst = instances[i];
    const mod = getComposeModule(inst.moduleId);
    if (!mod) continue;

    const stepId = inst.uid || encodeStepId(flowId, i + 1);
    const params = {
      ...(mod.defaults || {}),
      ...stripUiParams(inst.params || {}),
    };

    if (useRunTimeWindow && mod.kind === 'query') {
      params.time_window = '{{params.time_window}}';
    }

    for (const [param, rule] of Object.entries(mod.bindRules || {})) {
      const upstream = findUpstreamStep(built, rule.fromKind);
      if (upstream) {
        params[param] = `{{steps.${upstream.id}.${rule.field}}}`;
      }
    }

    const step = { id: stepId, kind: mod.kind, params };
    if (i > 0) {
      step.requires = [steps[i - 1].id];
    }
    steps.push(step);
    built.push({ id: stepId, kind: mod.kind, moduleId: inst.moduleId, label: mod.label });
  }

  return {
    params_schema: {
      time_window: { type: 'time_window', default: { preset: 'yesterday' }, label: '时间窗' },
    },
    steps,
  };
}

export function composeStepHints(stepInstances, index) {
  const inst = stepInstances[index];
  if (!inst) return [];
  const built = [];
  for (let i = 0; i < index; i += 1) {
    const m = getComposeModule(stepInstances[i].moduleId);
    if (m) {
      built.push({
        id: stepInstances[i].uid,
        kind: m.kind,
        label: m.label,
        moduleId: stepInstances[i].moduleId,
      });
    }
  }
  return bindHintsForModule(inst.moduleId, built);
}

/** @deprecated 使用 buildComposeDefinition */
export function buildLinearComposeDefinition(stepsConfig, flowId = DEFAULT_FLOW_ID) {
  const instances = DEFAULT_MODULE_IDS.map((moduleId) => ({
    moduleId,
    params: stepsConfig?.[moduleId] || {},
  }));
  return buildComposeDefinition(instances, { flowId });
}
