import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { inferPythonPresetsFromDraft } from '../lib/pythonPresets';
import {
  explicitPythonPresets,
  PRESET_ENV_KEYS,
  stripEnvSchemaForPreset,
} from '../lib/pythonPresetEnv';
import { flowHasRandomSample } from '../lib/strategyEnvSchema';

/**
 * 策略可加载的 Python 预设函数包（python_presets）
 */
export default function PythonPresetsEditor({ draft, onChange }) {
  const [catalog, setCatalog] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getPythonPresets()
      .then((r) => setCatalog(r.data?.groups || []))
      .catch(() => setCatalog([]))
      .finally(() => setLoading(false));
  }, []);

  const selected = new Set(draft?.python_presets || []);

  const toggle = (id) => {
    const next = new Set(selected);
    const turningOn = !next.has(id);
    if (turningOn) next.add(id);
    else next.delete(id);
    let envSchema = draft.env_schema || [];
    Object.keys(PRESET_ENV_KEYS).forEach((pid) => {
      envSchema = stripEnvSchemaForPreset({ env_schema: envSchema }, pid, next.has(pid));
    });
    onChange({ ...draft, python_presets: [...next], env_schema: envSchema });
  };

  const hasExplicitPresets = explicitPythonPresets(draft) !== null;
  const samplingOffButFlowHasBlock = hasExplicitPresets
    && !selected.has('sampling')
    && flowHasRandomSample(draft?.flow);

  const inferFromCode = () => {
    const inferred = inferPythonPresetsFromDraft(draft);
    onChange({ ...draft, python_presets: inferred.length ? inferred : ['observe', 'filter'] });
  };

  if (loading) return <p className="muted">加载预设函数目录…</p>;

  return (
    <div className="python-presets-editor">
      <div className="python-presets-head">
        <div>
          <h3 className="strategy-env-schema-title">预设 Python 函数</h3>
          <p className="strategy-panel-hint muted">
            查询页策略参数与勾选一致：勾选「采样」才有 SAMPLE_SIZE / RANDOM_SEED；未勾选的包不会加载其专属参数。
          </p>
          {samplingOffButFlowHasBlock && (
            <p className="strategy-panel-hint strategy-panel-warn">
              未勾选「采样」，但 Flow 仍含 random_sample 块：查询页不会显示采样参数，执行时该块也不会生效（请删除该块或重新勾选采样）。
            </p>
          )}
        </div>
        <button type="button" className="btn btn-sm btn-ghost" onClick={inferFromCode}>
          从代码推断
        </button>
      </div>
      <div className="python-presets-grid">
        {catalog.filter((g) => !g.always).map((g) => (
          <label key={g.id} className={`python-preset-card${selected.has(g.id) ? ' is-on' : ''}`}>
            <input
              type="checkbox"
              checked={selected.has(g.id)}
              onChange={() => toggle(g.id)}
            />
            <span className="python-preset-title">{g.label}</span>
            <span className="python-preset-desc">{g.description}</span>
            <span className="python-preset-fns">
              {(g.functions || []).map((f) => f.name).join(' · ')}
            </span>
            {(PRESET_ENV_KEYS[g.id] || []).length > 0 && (
              <span className="python-preset-env-keys muted">
                参数：{(PRESET_ENV_KEYS[g.id] || []).join(', ')}
              </span>
            )}
          </label>
        ))}
      </div>
    </div>
  );
}
