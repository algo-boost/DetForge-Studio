/** Python 预设包推断 */

export function inferPythonPresetsFromDraft(draft) {
  const selected = new Set(draft?.python_presets || []);
  const code = String(draft?.python_code || draft?.python || '');
  const inferred = [];
  if (code.includes('random_sample') || code.includes('sample_rows')) inferred.push('random_sample');
  if (code.includes('dedupe')) inferred.push('dedupe');
  return [...new Set([...selected, ...inferred])];
}
