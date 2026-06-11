/** 策略 env_schema 字段类型 */

export const ENV_FIELD_TYPES = [
  { id: 'text', label: '文本' },
  { id: 'number', label: '数字' },
  { id: 'datetime', label: '日期时间' },
  { id: 'select', label: '下拉单选' },
  { id: 'multiselect', label: '下拉多选' },
];

export function normalizeFieldType(type) {
  const t = String(type || 'text').toLowerCase();
  if (ENV_FIELD_TYPES.some((x) => x.id === t)) return t;
  return 'text';
}

export function fieldTypeNeedsOptions(type) {
  const t = normalizeFieldType(type);
  return t === 'select' || t === 'multiselect';
}

export function normalizeOptions(options) {
  if (!options) return [];
  if (Array.isArray(options)) {
    return options.map((o) => (typeof o === 'string' ? { value: o, label: o } : o));
  }
  return [];
}

export function optionsToText(options) {
  return normalizeOptions(options).map((o) => o.value ?? o.label).join('\n');
}

export function parseOptionsText(text) {
  return String(text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => ({ value: line, label: line }));
}

export function readEnvValue(values, key) {
  return values?.[String(key || '').toUpperCase()] ?? '';
}

export function formatFieldValueForEnv(type, value) {
  if (value == null) return '';
  if (normalizeFieldType(type) === 'multiselect' && Array.isArray(value)) {
    return value.join(',');
  }
  return String(value);
}

export function displayFieldValue(type, value) {
  if (value == null || value === '') return '—';
  if (normalizeFieldType(type) === 'multiselect' && Array.isArray(value)) {
    return value.join(', ');
  }
  return String(value);
}

export function parseMultiselectValue(raw) {
  if (Array.isArray(raw)) return raw;
  if (raw == null || raw === '') return [];
  return String(raw).split(',').map((s) => s.trim()).filter(Boolean);
}
