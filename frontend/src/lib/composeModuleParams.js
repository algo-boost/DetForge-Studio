/**
 * 组合编排：完整 UI 状态 ↔ workflow step params 序列化。
 * `_ui` 仅前端持久化，后端 step handler 会忽略未知字段。
 */

export function inferTimeWindowFromEnv(queryEnv, existing) {
  const start = String(queryEnv?.START_TIME || '').trim();
  const end = String(queryEnv?.END_TIME || '').trim();
  if (start && end) {
    return { preset: 'custom', start_time: start, end_time: end };
  }
  if (existing?.time_window) return existing.time_window;
  return { preset: 'yesterday' };
}

/** @param {object} state QueryPage 当前编辑态 */
export function buildQueryComposeParams(state) {
  const {
    strategyId,
    sql,
    pythonCode,
    sampleCode,
    filterMode,
    flow,
    dataSource,
    queryEnv,
    predictJobId,
    sampleSize,
    randomSeed,
    uiBackendMode,
    processPipeline,
    queryUiMode,
    existingParams = {},
  } = state;

  const strategy_snapshot = {
    sql_template: sql,
    python_code: pythonCode,
    sample_code: sampleCode || undefined,
    filter_mode: uiBackendMode,
    flow: filterMode === 'code' ? null : flow,
    process_pipeline: processPipeline?.length ? processPipeline : undefined,
    sample_size: sampleSize,
    random_seed: randomSeed,
  };

  return {
    ...(existingParams || {}),
    strategy_id: strategyId || '',
    time_window: inferTimeWindowFromEnv(queryEnv, existingParams),
    data_source: dataSource,
    env: queryEnv || {},
    predict_job_id: predictJobId || undefined,
    sample_size: sampleSize,
    random_seed: randomSeed,
    strategy_snapshot,
    _ui: {
      sql,
      pythonCode,
      sampleCode,
      filterMode,
      dataSource,
      queryEnv,
      predictJobId,
      sampleSize,
      randomSeed,
      queryUiMode,
      strategyId,
    },
  };
}

/** @param {object} panelState PlatformPredictPanel 当前编辑态 */
export function buildPredictComposeParams(panelState, existingParams = {}) {
  const {
    deploySelections,
    trainSelections,
    registrySelections,
    threshold,
    maxSize,
    device,
    intra,
    namePrefix,
    dataSourceType,
    datasetId,
    localDir,
    queryTaskId,
    queryIndices,
    projectId,
    selectedDeploy,
    selectedTrain,
    selectedRegistry,
  } = panelState;

  const firstDeploy = deploySelections[0];
  const firstTrain = trainSelections[0];
  const firstRegistry = registrySelections[0];

  const out = {
    ...(existingParams || {}),
    threshold: threshold !== '' ? Number(threshold) : 0.1,
    device: device?.trim() || '',
    max_size: maxSize !== '' ? Number(maxSize) : 1536,
    intra_concurrency: Number(intra) || 1,
    name: namePrefix?.trim() || undefined,
    _ui: {
      dataSourceType,
      datasetId,
      localDir,
      queryTaskId,
      queryIndices,
      threshold,
      maxSize,
      device,
      intra,
      namePrefix,
      projectId,
      selectedDeploy,
      selectedTrain,
      selectedRegistry,
      modelTab: panelState.modelTab,
    },
  };

  delete out.model_id;
  delete out.train_id;
  delete out.model_name;

  if (firstDeploy != null) {
    out.model_id = Number(firstDeploy);
  } else if (firstTrain != null) {
    out.train_id = Number(firstTrain);
  } else if (firstRegistry != null) {
    out.model_id = Number(firstRegistry);
  }

  if (deploySelections.length > 1 || trainSelections.length > 1 || registrySelections.length > 1) {
    out._ui.multiModelNote = '编排每步仅执行首个所选模型；多模型请添加多个预测步骤';
  }

  return out;
}

export function validateComposeStep(moduleId, params, bindHints = []) {
  const missing = bindHints.find((h) => !h.ok);
  if (missing) return missing.text;

  switch (moduleId) {
    case 'query':
    case 'query_predict':
      if (!params?.strategy_id && !params?.strategy_snapshot?.sql_template) {
        return '请选择策略或配置 SQL';
      }
      return null;
    case 'predict':
      if (!params?.model_id && !params?.train_id) {
        return '请至少选择一个模型';
      }
      return null;
    case 'curation_create':
      return null;
    default:
      return null;
  }
}
