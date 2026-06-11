/** 策略环境变量：本地持久化与 schema 辅助。 */

export { formatEnvDateTime } from './time';

const ENV_KEY_PREFIX = 'pc_env_';

/** 仅系统自动注入，不可在策略「可调参数」中定义 */
export const RUNTIME_SYSTEM_VARS = new Set([
  'START_TIME', 'END_TIME', 'JOB_ID', 'PREDICT_JOB_ID', 'DATA_SOURCE',
  'THRESHOLD', 'MODEL_ID', 'MODEL_NAME', 'RUN_ID', 'STAGE',
]);

/** 与 RUNTIME_SYSTEM_VARS 同义（策略 schema 编辑器用） */
export const RUNTIME_AUTO_VARS = RUNTIME_SYSTEM_VARS;

export const SYSTEM_VAR_HINTS = Object.fromEntries(
  Object.entries({
    START_TIME: '开始时间（工具栏时段）',
    END_TIME: '结束时间（工具栏时段）',
    JOB_ID: '预测作业 ID（自动）',
    PREDICT_JOB_ID: '预测作业 ID（自动）',
    DATA_SOURCE: '数据源（自动）',
    THRESHOLD: '预测阈值（自动）',
    MODEL_ID: '模型 ID（自动）',
    MODEL_NAME: '模型名称（自动）',
    RUN_ID: '回跑任务 ID（自动）',
    STAGE: '阶段（自动）',
  }),
);

export const RUNTIME_VAR_LABELS = {
  START_TIME: '开始时间（工具栏时段）',
  END_TIME: '结束时间（工具栏时段）',
  JOB_ID: '预测作业 ID（自动）',
  PREDICT_JOB_ID: '预测作业 ID（自动）',
  DATA_SOURCE: '数据源（自动）',
  THRESHOLD: '预测阈值（自动）',
  MODEL_ID: '模型 ID（自动）',
  MODEL_NAME: '模型名称（自动）',
  RUN_ID: '回跑任务 ID（自动）',
  STAGE: '阶段（自动）',
};

export const RUNTIME_VAR_HINT = Object.entries(RUNTIME_VAR_LABELS)
  .map(([k, label]) => `${label} → \${${k}}`)
  .join(' · ');

export function mergeEnvOverrides(base, overrides) {
  const out = { ...(base || {}) };
  Object.entries(overrides || {}).forEach(([k, v]) => {
    const key = String(k).trim().toUpperCase();
    if (!key) return;
    if (v == null || String(v).trim() === '') delete out[key];
    else out[key] = String(v).trim();
  });
  return out;
}

export function mergeEnvMaps(...maps) {
  return mergeEnvOverrides({}, Object.assign({}, ...maps));
}

export function envDefaultsFromSchema(schema) {
  const out = {};
  for (const row of schema || []) {
    const key = String(row?.key || '').trim().toUpperCase();
    if (!key) continue;
    const val = row?.default ?? row?.placeholder;
    if (val != null && String(val).trim() !== '') out[key] = String(val).trim();
  }
  return out;
}

/** 从策略 + 历史值构建初始 env（含 sample_size 等 legacy 字段回落） */
export function buildStrategyEnvDefaults(schema, strategyMeta = {}, saved = {}) {
  const defaults = envDefaultsFromSchema(schema);
  if (!defaults.SAMPLE_SIZE && strategyMeta.sample_size != null) {
    defaults.SAMPLE_SIZE = String(strategyMeta.sample_size);
  }
  if (!defaults.RANDOM_SEED && strategyMeta.random_seed != null) {
    defaults.RANDOM_SEED = String(strategyMeta.random_seed);
  }
  return mergeEnvMaps(defaults, saved);
}

export function parseEnvSampleSize(env, fallback = 300) {
  const v = parseInt(env?.SAMPLE_SIZE, 10);
  return Number.isFinite(v) && v > 0 ? v : fallback;
}

/** 仅当 env 显式含 SAMPLE_SIZE 时返回；否则 null（不二次采样） */
export function parseEnvSampleSizeOptional(env) {
  if (!env || env.SAMPLE_SIZE == null || String(env.SAMPLE_SIZE).trim() === '') return null;
  const v = parseInt(env.SAMPLE_SIZE, 10);
  return Number.isFinite(v) && v > 0 ? v : null;
}

export function parseEnvRandomSeed(env, fallback = 42) {
  const v = parseInt(env?.RANDOM_SEED, 10);
  return Number.isFinite(v) ? v : fallback;
}

export function envSummary(env, schema) {
  const keys = Object.keys(env || {});
  if (!keys.length) return '';
  const labelMap = Object.fromEntries(
    (schema || []).map((r) => [String(r.key).toUpperCase(), r.label || r.key]),
  );
  return keys.map((k) => `${labelMap[k] || k}=${env[k]}`).join(' · ');
}

export function loadStrategyEnv(strategyId) {
  if (!strategyId) return {};
  try {
    const raw = localStorage.getItem(`${ENV_KEY_PREFIX}${strategyId}`);
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

export function saveStrategyEnv(strategyId, env) {
  if (!strategyId) return;
  try {
    localStorage.setItem(`${ENV_KEY_PREFIX}${strategyId}`, JSON.stringify(env || {}));
  } catch { /* ignore */ }
}

export function buildStageEnvPayload(stage1Env, stage2Env) {
  const payload = {};
  if (stage1Env && Object.keys(stage1Env).length) payload.stage1_env = stage1Env;
  if (stage2Env && Object.keys(stage2Env).length) payload.stage2_env = stage2Env;
  return payload;
}

export function newEnvSchemaRow(key = '', label = '') {
  return {
    key: String(key).toUpperCase(),
    label: label || key,
    type: 'text',
    default: '',
    placeholder: '',
    description: '',
  };
}

/** 从 SQL / Python 文本推断自定义变量（策略编辑用） */
export function inferEnvSchemaFromTexts(...texts) {
  const found = new Set();
  const varRe = /\$\{([A-Z][A-Z0-9_]*)\}/g;
  const getEnvRe = /get_env\s*\(\s*['"]([A-Z][A-Z0-9_]*)['"]/gi;
  for (const text of texts) {
    if (!text) continue;
    const s = String(text);
    let m;
    varRe.lastIndex = 0;
    while ((m = varRe.exec(s))) found.add(m[1].toUpperCase());
    getEnvRe.lastIndex = 0;
    while ((m = getEnvRe.exec(s))) found.add(m[1].toUpperCase());
  }
  return [...found]
    .filter((k) => !RUNTIME_SYSTEM_VARS.has(k))
    .sort()
    .map((k) => newEnvSchemaRow(k, k));
}

/** 从 SQL 文本提取 ${VAR} 占位符 */
export function extractSqlTemplateVars(sql) {
  const found = new Set();
  const re = /\$\{([A-Z][A-Z0-9_]*)\}/g;
  let m;
  const s = String(sql || '');
  while ((m = re.exec(s))) found.add(m[1]);
  return [...found];
}

export function mergeEnvSchema(existing, inferred) {
  const map = new Map((existing || []).map((r) => [String(r.key).toUpperCase(), { ...r }]));
  for (const row of inferred || []) {
    const k = String(row.key).toUpperCase();
    if (!map.has(k)) map.set(k, row);
  }
  return [...map.values()];
}

/** SQL/环境变量时间 → datetime-local 控件值 */
export function toDatetimeLocalValue(value) {
  if (value == null || String(value).trim() === '') return '';
  const s = String(value).trim().replace(' ', 'T');
  return s.length >= 16 ? s.slice(0, 16) : s;
}

export function newVarRow(key = '', label = '') {
  return {
    key: String(key || '').toUpperCase(),
    label: label || key || '',
    value: '',
  };
}

export function profileVarsToEnv(profile) {
  const out = {};
  for (const row of profile?.vars || []) {
    const k = String(row?.key || '').trim().toUpperCase();
    if (!k) continue;
    const v = row?.value;
    if (v != null && String(v).trim() !== '') out[k] = String(v).trim();
  }
  return out;
}
