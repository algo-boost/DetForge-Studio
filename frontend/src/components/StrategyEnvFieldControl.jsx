import {
  displayFieldValue,
  fieldTypeNeedsOptions,
  formatFieldValueForEnv,
  normalizeFieldType,
  normalizeOptions,
  parseMultiselectValue,
  readEnvValue,
} from '../lib/envFieldTypes';

/**
 * 按 env_schema.type 渲染单个策略参数字段
 */
export default function StrategyEnvFieldControl({
  field,
  values,
  onChange,
  testIdPrefix = 'strategy-env',
  className = 'strategy-env-field',
}) {
  const type = normalizeFieldType(field?.type);
  const options = normalizeOptions(field?.options);
  const label = field?.label || field?.key;
  const testId = `${testIdPrefix}-${field.key}`;

  const commit = (raw) => {
    const val = formatFieldValueForEnv(field, raw);
    const key = String(field.key).toUpperCase();
    onChange(key, val);
  };

  if (type === 'select' && options.length > 0) {
    return (
      <label className={className}>
        <span className="strategy-env-field-label">{label}</span>
        <select
          value={readEnvValue(values, field.key)}
          title={field.description || field.key}
          onChange={(e) => commit(e.target.value)}
          data-testid={testId}
        >
          <option value="">（请选择）</option>
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
      </label>
    );
  }

  if (type === 'multiselect' && options.length > 0) {
    const selected = new Set(parseMultiselectValue(readEnvValue(values, field.key)));
    const toggle = (value) => {
      const next = new Set(selected);
      if (next.has(value)) next.delete(value);
      else next.add(value);
      commit([...next]);
    };
    return (
      <div className={`${className} strategy-env-field-multiselect`}>
        <span className="strategy-env-field-label">{label}</span>
        <select
          multiple
          size={Math.min(6, Math.max(3, options.length))}
          title={field.description || 'Ctrl+点击多选'}
          data-testid={testId}
          value={[...selected]}
          onChange={(e) => {
            const next = [...e.target.selectedOptions].map((o) => o.value);
            commit(next);
          }}
        >
          {options.map((opt) => (
            <option key={opt.value} value={opt.value}>{opt.label}</option>
          ))}
        </select>
        <div className="strategy-env-multiselect-chips" role="group" aria-label={`${label} 快捷选择`}>
          {options.map((opt) => (
            <button
              key={opt.value}
              type="button"
              className={`strategy-env-chip${selected.has(opt.value) ? ' is-on' : ''}`}
              onClick={() => toggle(opt.value)}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'number') {
    return (
      <label className={className}>
        <span className="strategy-env-field-label">{label}</span>
        <input
          type="number"
          step={field.step ?? 'any'}
          min={field.min}
          max={field.max}
          placeholder={field.placeholder ?? field.default ?? ''}
          title={field.description || field.key}
          value={displayFieldValue(field, values)}
          onChange={(e) => commit(e.target.value)}
          data-testid={testId}
        />
      </label>
    );
  }

  if (type === 'datetime') {
    return (
      <label className={className}>
        <span className="strategy-env-field-label">{label}</span>
        <input
          type="datetime-local"
          step={60}
          placeholder={field.placeholder || 'YYYY-MM-DD HH:MM'}
          title={field.description || field.key}
          value={displayFieldValue(field, values)}
          onChange={(e) => commit(e.target.value)}
          data-testid={testId}
        />
      </label>
    );
  }

  return (
    <label className={className}>
      <span className="strategy-env-field-label">{label}</span>
      <input
        type="text"
        placeholder={field.placeholder ?? field.default ?? ''}
        title={field.description || field.key}
        value={displayFieldValue(field, values)}
        onChange={(e) => commit(e.target.value)}
        data-testid={testId}
      />
    </label>
  );
}
