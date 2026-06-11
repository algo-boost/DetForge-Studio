/** Python 预设与环境变量 schema 交叉 */

export const PRESET_ENV_KEYS = new Set(['SAMPLE_SIZE', 'RANDOM_SEED']);

export function explicitPythonPresets(draft) {
  return [...(draft?.python_presets || [])];
}

export function stripEnvSchemaForPreset(schema, presetId) {
  if (presetId === 'random_sample') {
    return (schema || []).filter((row) => !PRESET_ENV_KEYS.has(String(row?.key || '').toUpperCase()));
  }
  return schema || [];
}
