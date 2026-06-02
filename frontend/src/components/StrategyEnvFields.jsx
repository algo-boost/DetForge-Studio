import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { formatEnvDateTime } from '../lib/envVars';
import { setTimePreset } from '../lib/time';
import StrategyEnvFieldControl from './StrategyEnvFieldControl';

const TIME_PRESETS = [
  { id: 'today', label: '今天' },
  { id: 'yesterday', label: '昨天' },
  { id: '7days', label: '近 7 天' },
  { id: '30days', label: '近 30 天' },
];

function applyTimePreset(preset) {
  const r = setTimePreset(preset);
  return {
    START_TIME: formatEnvDateTime(r.start),
    END_TIME: formatEnvDateTime(r.end),
  };
}

/**
 * 策略可调参数（按类型渲染控件，查询 / 回跑共用）
 */
function normalizeTimeFieldTypes(rows) {
  return (rows || []).map((row) => {
    const key = String(row?.key || '').toUpperCase();
    if (key === 'START_TIME' || key === 'END_TIME') {
      return { ...row, key, type: 'datetime' };
    }
    return row;
  });
}

export default function StrategyEnvFields({
  strategyId,
  schema: schemaProp,
  values,
  onChange,
  onStale,
  title = '策略参数',
  compact = false,
  testId = 'strategy-env-fields',
}) {
  const [fetchedSchema, setFetchedSchema] = useState([]);
  const [loading, setLoading] = useState(false);

  const useParentSchema = Array.isArray(schemaProp) && schemaProp.length > 0;

  useEffect(() => {
    if (useParentSchema) {
      setFetchedSchema([]);
      setLoading(false);
      return;
    }
    if (!strategyId) {
      setFetchedSchema([]);
      return;
    }
    setLoading(true);
    api.getStrategyVariables(strategyId)
      .then((r) => setFetchedSchema(normalizeTimeFieldTypes(r.data?.custom_vars || [])))
      .catch(() => setFetchedSchema([]))
      .finally(() => setLoading(false));
  }, [strategyId, useParentSchema]);

  const schema = useMemo(
    () => normalizeTimeFieldTypes(useParentSchema ? schemaProp : fetchedSchema),
    [useParentSchema, schemaProp, fetchedSchema],
  );

  const hasTimeFields = useMemo(
    () => schema.some((f) => f.key === 'START_TIME' || f.key === 'END_TIME'),
    [schema],
  );

  if (!schema.length && !loading) return null;

  const setField = (key, val) => {
    onChange({ ...values, [String(key).toUpperCase()]: val });
    onStale?.();
  };

  const applyPreset = (presetId) => {
    onChange({ ...values, ...applyTimePreset(presetId) });
    onStale?.();
  };

  return (
    <div
      className={`strategy-env-fields${compact ? ' is-compact' : ''}`}
      data-testid={testId}
    >
      <span className="strategy-env-fields-title">{title}</span>
      {hasTimeFields && (
        <div className="strategy-env-time-presets">
          <span className="muted strategy-env-time-label">时段快捷</span>
          <div className="time-presets">
            {TIME_PRESETS.map((p) => (
              <button
                key={p.id}
                type="button"
                className="preset-btn"
                onClick={() => applyPreset(p.id)}
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className="strategy-env-fields-grid">
        {loading ? (
          <span className="muted strategy-env-loading">加载参数…</span>
        ) : (
          schema.map((field) => (
            <StrategyEnvFieldControl
              key={field.key}
              field={field}
              values={values}
              onChange={setField}
              testIdPrefix="strategy-env"
            />
          ))
        )}
      </div>
    </div>
  );
}
