import { useEffect, useState } from 'react';
import { api } from '../api/client';

/**
 * 策略可调参数（来自策略 env_schema，查询 / 回跑共用）
 * label 为中文名，直接展示给用户。
 */
export default function StrategyEnvFields({
  strategyId,
  values,
  onChange,
  onStale,
  title = '策略参数',
  compact = false,
  testId = 'strategy-env-fields',
}) {
  const [schema, setSchema] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!strategyId) {
      setSchema([]);
      return;
    }
    setLoading(true);
    api.getStrategyVariables(strategyId)
      .then((r) => setSchema(r.data?.custom_vars || []))
      .catch(() => setSchema([]))
      .finally(() => setLoading(false));
  }, [strategyId]);

  if (!strategyId) return null;
  if (!loading && !schema.length) return null;

  const setField = (key, val) => {
    const next = { ...values, [String(key).toUpperCase()]: val };
    onChange(next);
    onStale?.();
  };

  return (
    <div
      className={`strategy-env-fields${compact ? ' is-compact' : ''}`}
      data-testid={testId}
    >
      <span className="strategy-env-fields-title">{title}</span>
      <div className="strategy-env-fields-grid">
        {(loading ? [{ key: '_loading', label: '加载中…' }] : schema).map((field) => (
          field.key === '_loading' ? (
            <span key="_loading" className="muted strategy-env-loading">加载参数…</span>
          ) : (
            <label key={field.key} className="strategy-env-field">
              <span className="strategy-env-field-label">{field.label || field.key}</span>
              <input
                type={field.type === 'number' ? 'number' : 'text'}
                step={field.type === 'number' ? '0.01' : undefined}
                placeholder={field.placeholder || field.default || ''}
                title={field.description || field.key}
                value={values[field.key] ?? values[field.key?.toUpperCase()] ?? ''}
                onChange={(e) => setField(field.key, e.target.value)}
                data-testid={`strategy-env-${field.key}`}
              />
            </label>
          )
        ))}
      </div>
    </div>
  );
}
