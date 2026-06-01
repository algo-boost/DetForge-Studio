import { useEffect, useState } from 'react';
import { api } from '../api/client';

/** 查询页内联环境变量（与策略绑定，供 SQL / Python ${VAR} 使用） */
export default function QueryEnvSection({ strategyId, values, onChange, onStale }) {
  const [schema, setSchema] = useState([]);

  useEffect(() => {
    if (!strategyId) {
      setSchema([]);
      return;
    }
    api.getStrategyVariables(strategyId)
      .then((r) => setSchema(r.data?.custom_vars || []))
      .catch(() => setSchema([]));
  }, [strategyId]);

  if (!schema.length) return null;

  const setField = (key, val) => {
    const next = { ...values, [String(key).toUpperCase()]: val };
    onChange(next);
    onStale?.();
  };

  return (
    <div className="query-env-section" data-testid="query-env-section">
      <span className="query-env-label">环境变量</span>
      <div className="query-env-fields">
        {schema.map((field) => (
          <label key={field.key} className="query-env-field">
            <span>{field.label || field.key}</span>
            <input
              type={field.type === 'number' ? 'number' : 'text'}
              step={field.type === 'number' ? '0.01' : undefined}
              placeholder={field.placeholder || field.default || ''}
              value={values[field.key] ?? ''}
              onChange={(e) => setField(field.key, e.target.value)}
              data-testid={`query-env-${field.key}`}
            />
          </label>
        ))}
      </div>
      <span className="muted query-env-hint">SQL {'${KEY}'} · Python get_env('KEY')</span>
    </div>
  );
}
