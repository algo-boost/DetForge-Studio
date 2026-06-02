import { useMemo, useState } from 'react';
import {
  inferEnvSchemaFromTexts,
  mergeEnvSchema,
  newEnvSchemaRow,
  RUNTIME_AUTO_VARS,
  RUNTIME_VAR_HINT,
} from '../lib/envVars';
import {
  ENV_FIELD_TYPES,
  fieldTypeNeedsOptions,
  normalizeFieldType,
  optionsToText,
  parseOptionsText,
} from '../lib/envFieldTypes';
import { mergeStrategyEnvSchema, SAMPLING_ENV_KEYS } from '../lib/strategyEnvSchema';
import StrategyEnvFieldControl from './StrategyEnvFieldControl';

function normalizeSchemaTypes(rows) {
  return (rows || []).map((row) => {
    const key = String(row?.key || '').toUpperCase();
    if (key === 'START_TIME' || key === 'END_TIME') {
      return { ...row, key, type: 'datetime' };
    }
    return { ...row, type: normalizeFieldType(row?.type) };
  });
}

/**
 * 策略可调参数编排：支持文本 / 数字 / 时间 / 下拉单选 / 下拉多选，带实时预览
 */
export default function StrategyEnvSchemaEditor({ draft, onChange, templates = {} }) {
  const schema = useMemo(
    () => normalizeSchemaTypes(draft?.env_schema || []),
    [draft?.env_schema],
  );
  const [previewValues, setPreviewValues] = useState({});

  const updateSchema = (nextSchema) => {
    onChange({ ...draft, env_schema: normalizeSchemaTypes(nextSchema) });
  };

  const updateRow = (idx, patch) => {
    const key = String(patch.key ?? schema[idx]?.key ?? '').toUpperCase();
    if (patch.key != null && RUNTIME_AUTO_VARS.has(key)) return;
    const next = schema.map((row, i) => (
      i === idx ? { ...row, ...patch, key: key || row.key, type: normalizeFieldType(patch.type ?? row.type) } : row
    ));
    updateSchema(next);
  };

  const addRow = (type = 'text') => {
    updateSchema([...schema, { ...newEnvSchemaRow(), type: normalizeFieldType(type) }]);
  };

  const removeRow = (idx) => updateSchema(schema.filter((_, i) => i !== idx));

  const inferFromCode = () => {
    const inferred = inferEnvSchemaFromTexts(
      draft?.sql_template,
      draft?.python_code,
      draft?.filter_rules_code,
      draft?.sample_code,
    );
    updateSchema(mergeEnvSchema(schema, inferred));
  };

  const syncFromFlow = () => {
    updateSchema(mergeStrategyEnvSchema(draft, templates));
  };

  const activePresets = draft?.python_presets;
  const hasOrphanSamplingKeys = Array.isArray(activePresets)
    && !activePresets.includes('sampling')
    && schema.some((r) => SAMPLING_ENV_KEYS.has(String(r.key || '').toUpperCase()));

  const setPreviewField = (key, val) => {
    setPreviewValues((prev) => ({ ...prev, [String(key).toUpperCase()]: val }));
  };

  return (
    <div className="strategy-env-schema-editor">
      <div className="strategy-env-schema-head">
        <div>
          <h3 className="strategy-env-schema-title">可调参数编排</h3>
          <p className="strategy-panel-hint">
            为每个变量选择<strong>格式类型</strong>，查询页/回跑将渲染对应控件。SQL：
            <code>{' ${KEY} '}</code>
            Python：
            <code>get_env(&apos;KEY&apos;)</code>
            ；多选写入 env 为逗号分隔。
          </p>
          <p className="muted strategy-env-schema-reserved">
            仅下列键由运行时自动注入，请勿重复定义：
            {RUNTIME_VAR_HINT}
          </p>
        </div>
        <div className="strategy-env-schema-actions">
          <button type="button" className="btn btn-sm btn-ghost" onClick={inferFromCode}>从 SQL/Python 推断</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={syncFromFlow}>从 Flow 块合并</button>
        </div>
      </div>

      {hasOrphanSamplingKeys && (
        <p className="strategy-panel-hint strategy-panel-warn">
          未勾选预设「采样」，但编排里仍有采样参数。点击「从 Flow 同步」或保存后将按勾选自动移除。
        </p>
      )}

      <div className="strategy-env-type-toolbar">
        <span className="strategy-env-type-toolbar-label">快速添加</span>
        {ENV_FIELD_TYPES.map((t) => (
          <button
            key={t.id}
            type="button"
            className="btn btn-sm btn-ghost strategy-env-type-add"
            onClick={() => addRow(t.id)}
          >
            + {t.label}
          </button>
        ))}
      </div>

      {schema.length === 0 ? (
        <p className="muted strategy-env-schema-empty">
          暂无参数。点击上方「+ 文本 / + 数字 / + 时间字符串 / + 下拉单选 / + 下拉多选」添加，或从 SQL/Python、Flow 合并。
        </p>
      ) : (
        <div className="strategy-env-schema-cards">
          {schema.map((row, idx) => {
            const ftype = normalizeFieldType(row.type);
            const needsOpts = fieldTypeNeedsOptions(ftype);
            const previewField = { ...row, type: ftype };
            return (
              <div key={`${row.key}-${idx}`} className="strategy-env-schema-card">
                <div className="strategy-env-schema-card-head">
                  <div className="strategy-env-schema-card-meta">
                    <input
                      className="strategy-env-key-input"
                      value={row.key || ''}
                      placeholder="KEY"
                      readOnly={RUNTIME_AUTO_VARS.has(String(row.key || '').toUpperCase())}
                      onChange={(e) => updateRow(idx, { key: e.target.value.toUpperCase() })}
                    />
                    <input
                      value={row.label || ''}
                      placeholder="中文显示名"
                      onChange={(e) => updateRow(idx, { label: e.target.value })}
                    />
                  </div>
                  <button type="button" className="btn btn-sm btn-ghost strategy-action-danger" onClick={() => removeRow(idx)}>删除</button>
                </div>

                <div className="strategy-env-type-chips" role="group" aria-label="格式类型">
                  {ENV_FIELD_TYPES.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      className={`strategy-env-type-chip${ftype === t.id ? ' is-active' : ''}`}
                      onClick={() => {
                        const patch = { type: t.id };
                        if (!fieldTypeNeedsOptions(t.id)) patch.options = undefined;
                        updateRow(idx, patch);
                      }}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                <div className="strategy-env-schema-card-config">
                  {needsOpts ? (
                    <label className="strategy-env-config-block">
                      <span>选项列表（每行一项，支持 value 或 value|显示名）</span>
                      <textarea
                        className="strategy-env-options-input"
                        rows={4}
                        value={row._optionsText ?? optionsToText(row.options)}
                        onChange={(e) => {
                          const text = e.target.value;
                          updateRow(idx, { _optionsText: text, options: parseOptionsText(text) });
                        }}
                      />
                    </label>
                  ) : ftype === 'number' ? (
                    <div className="strategy-env-number-config">
                      <label>
                        <span>默认值</span>
                        <input
                          type="number"
                          value={row.default ?? ''}
                          onChange={(e) => updateRow(idx, { default: e.target.value })}
                        />
                      </label>
                      <label>
                        <span>最小</span>
                        <input
                          type="number"
                          value={row.min ?? ''}
                          onChange={(e) => updateRow(idx, { min: e.target.value })}
                        />
                      </label>
                      <label>
                        <span>最大</span>
                        <input
                          type="number"
                          value={row.max ?? ''}
                          onChange={(e) => updateRow(idx, { max: e.target.value })}
                        />
                      </label>
                      <label>
                        <span>步长</span>
                        <input
                          type="number"
                          value={row.step ?? ''}
                          onChange={(e) => updateRow(idx, { step: e.target.value })}
                        />
                      </label>
                    </div>
                  ) : (
                    <label className="strategy-env-config-block">
                      <span>{ftype === 'datetime' ? '默认时间（可留空，查询页用快捷时段填充）' : '默认值'}</span>
                      <input
                        type={ftype === 'datetime' ? 'datetime-local' : 'text'}
                        step={ftype === 'datetime' ? 60 : undefined}
                        value={row.default ?? ''}
                        placeholder={ftype === 'datetime' ? '' : '默认'}
                        onChange={(e) => updateRow(idx, {
                          default: ftype === 'datetime'
                            ? e.target.value.replace('T', ' ').slice(0, 19)
                            : e.target.value,
                        })}
                      />
                    </label>
                  )}
                  <label className="strategy-env-config-block strategy-env-config-desc">
                    <span>说明</span>
                    <input
                      value={row.description || ''}
                      placeholder="给使用者的提示"
                      onChange={(e) => updateRow(idx, { description: e.target.value })}
                    />
                  </label>
                </div>

                <div className="strategy-env-schema-preview">
                  <span className="strategy-env-preview-label">查询页预览</span>
                  <StrategyEnvFieldControl
                    field={previewField}
                    values={previewValues}
                    onChange={setPreviewField}
                    testIdPrefix={`preview-${row.key}`}
                    className="strategy-env-field"
                  />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
