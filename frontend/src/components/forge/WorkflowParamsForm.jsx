import { useEffect, useState } from 'react';
import { api } from '../../api/client';
import { TIME_WINDOW_PRESETS } from '../../lib/workflowCatalog';

/**
 * 根据 params_schema 渲染表单，替代手写 JSON。
 */
export default function WorkflowParamsForm({ schema = {}, value = {}, onChange, models = [] }) {
  const [strategies, setStrategies] = useState([]);

  useEffect(() => {
    api.getStrategies().then((r) => {
      const data = r.data || r.strategies || {};
      const list = Array.isArray(data)
        ? data
        : Object.entries(data).map(([id, s]) => ({ id, name: s.name || id, ...s }));
      setStrategies(list);
    }).catch(() => setStrategies([]));
  }, []);

  const entries = Object.entries(schema);
  if (!entries.length) {
    return <p className="wf-muted">此模板无需额外参数</p>;
  }

  const set = (key, val) => onChange({ ...value, [key]: val });

  return (
    <div className="wf-params-form">
      {entries.map(([key, spec]) => {
        const label = spec.label || key;
        const type = spec.type || 'string';
        const val = value[key] ?? spec.default;

        if (type === 'strategy') {
          return (
            <label key={key} className="wf-param-row">
              <span>{label}{spec.required ? ' *' : ''}</span>
              <select
                className="form-select"
                value={val || ''}
                onChange={(e) => set(key, e.target.value)}
              >
                <option value="">选择策略…</option>
                {strategies.map((s) => (
                  <option key={s.id} value={s.id}>{s.name || s.id}</option>
                ))}
              </select>
            </label>
          );
        }

        if (type === 'model') {
          return (
            <label key={key} className="wf-param-row">
              <span>{label}{spec.required ? ' *' : ''}</span>
              <select
                className="form-select"
                value={val ?? ''}
                onChange={(e) => set(key, e.target.value ? Number(e.target.value) : '')}
              >
                <option value="">选择模型…</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>{m.name || `#${m.id}`}</option>
                ))}
              </select>
            </label>
          );
        }

        if (type === 'time_window') {
          const preset = (typeof val === 'object' && val?.preset) ? val.preset : (val || 'yesterday');
          return (
            <label key={key} className="wf-param-row">
              <span>{label}</span>
              <select
                className="form-select"
                value={preset}
                onChange={(e) => set(key, { preset: e.target.value })}
              >
                {TIME_WINDOW_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>{p.label}</option>
                ))}
              </select>
            </label>
          );
        }

        if (type === 'number') {
          return (
            <label key={key} className="wf-param-row">
              <span>{label}</span>
              <input
                className="form-input"
                type="number"
                step="any"
                value={val ?? ''}
                onChange={(e) => set(key, e.target.value === '' ? '' : Number(e.target.value))}
              />
            </label>
          );
        }

        return (
          <label key={key} className="wf-param-row">
            <span>{label}</span>
            <input
              className="form-input"
              type="text"
              value={val ?? ''}
              onChange={(e) => set(key, e.target.value)}
            />
          </label>
        );
      })}
    </div>
  );
}
