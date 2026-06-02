import { useEffect, useState } from 'react';
import { api } from '../api/client';
import StrategyEnvFieldControl from './StrategyEnvFieldControl';

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
    onChange({ ...values, [String(key).toUpperCase()]: val });
    onStale?.();
  };

  return (
    <div className="query-env-section" data-testid="query-env-section">
      <span className="query-env-label">环境变量</span>
      <div className="query-env-fields">
        {schema.map((field) => (
          <StrategyEnvFieldControl
            key={field.key}
            field={field}
            values={values}
            onChange={setField}
            testIdPrefix="query-env"
            className="query-env-field strategy-env-field"
          />
        ))}
      </div>
      <span className="muted query-env-hint">SQL {'${KEY}'} · Python get_env('KEY')</span>
    </div>
  );
}
