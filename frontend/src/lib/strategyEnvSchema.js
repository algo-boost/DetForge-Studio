/** 策略 env_schema 与时间字段辅助 */

export const TIME_ENV_FIELDS = new Set(['START_TIME', 'END_TIME']);

export const SAMPLING_ENV_KEYS = new Set(['SAMPLE_SIZE', 'RANDOM_SEED']);

export function mergeStrategyEnvSchema(existing = [], inferred = []) {
  const map = new Map((existing || []).map((r) => [String(r.key).toUpperCase(), { ...r }]));
  for (const row of inferred || []) {
    const k = String(row.key).toUpperCase();
    if (!map.has(k)) map.set(k, row);
  }
  return [...map.values()];
}

export function flowHasRandomSample(flow) {
  const nodes = flow?.nodes || [];
  return nodes.some((n) => {
    const t = String(n?.type || n?.kind || '');
    return t.includes('sample') || t.includes('random');
  });
}
