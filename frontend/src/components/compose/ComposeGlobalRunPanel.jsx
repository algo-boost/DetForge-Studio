import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../../api/client';
import { GlobalEnvEditor } from '../EnvVarPanel';
import {
  defaultInputsForTemplate,
  normalizeEnvSpec,
  normalizeRunParamsDefaults,
} from '../../lib/runEnvSpec';
import {
  envDictToRows,
  envRowsToDict,
  patchGlobalEnvRows,
} from '../../lib/envVars';

export { envDictToRows, envRowsToDict };

function RunEnvTemplateFields({ schema, inputs, onChange }) {
  if (!schema?.length) return null;
  return (
    <div className="run-env-template-fields">
      {schema.map((field) => {
        const key = field.key;
        const val = inputs?.[key] ?? field.default ?? '';
        if (field.type === 'select' && field.options?.length) {
          return (
            <label key={key} className="run-env-template-field">
              <span>{field.label || key}</span>
              <select
                className="form-select"
                value={val}
                onChange={(e) => onChange({ ...inputs, [key]: e.target.value })}
              >
                {field.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>{opt.label}</option>
                ))}
              </select>
            </label>
          );
        }
        return (
          <label key={key} className="run-env-template-field">
            <span>{field.label || key}</span>
            <input
              className="form-input"
              type={field.type === 'number' ? 'number' : 'text'}
              placeholder={field.placeholder || ''}
              value={val}
              onChange={(e) => onChange({ ...inputs, [key]: e.target.value })}
            />
          </label>
        );
      })}
    </div>
  );
}

/**
 * 组合编排页头：env 模板 + 入参 + 脚本预览 + 额外静态 env。
 */
export default function ComposeGlobalRunPanel({
  flowId,
  runParamsDefaults,
  onRunParamsDefaultsChange,
  extraEnvRows,
  onExtraEnvRowsChange,
}) {
  const [templates, setTemplates] = useState([]);
  const [previewEnv, setPreviewEnv] = useState({});
  const [previewError, setPreviewError] = useState('');
  const [loadingPreview, setLoadingPreview] = useState(false);

  const templatesById = useMemo(
    () => Object.fromEntries(templates.map((t) => [t.id, t])),
    [templates],
  );

  const normalized = useMemo(
    () => normalizeRunParamsDefaults(runParamsDefaults, templatesById),
    [runParamsDefaults, templatesById],
  );

  const envSpec = normalized.env_spec || {};
  const templateId = envSpec.template_id || 'time_preset';
  const activeTemplate = templatesById[templateId];

  useEffect(() => {
    api.forgeRunEnvTemplates('?include_script=1').then((r) => {
      if (r.success) setTemplates(r.data || []);
    }).catch(() => {});
  }, []);

  const refreshPreview = useCallback(async (params) => {
    setLoadingPreview(true);
    setPreviewError('');
    try {
      const r = await api.forgeRunEnvPreview({
        env_spec: params.env_spec,
        env: params.env,
        flow_id: flowId && flowId !== 'flow_draft' ? flowId : undefined,
      });
      if (r.success) {
        setPreviewEnv(r.data?.env || {});
      } else {
        setPreviewError(r.error || '预览失败');
      }
    } catch (e) {
      setPreviewError(e.message || String(e));
      setPreviewEnv({});
    } finally {
      setLoadingPreview(false);
    }
  }, [flowId]);

  useEffect(() => {
    if (!templates.length) return undefined;
    const timer = setTimeout(() => refreshPreview(normalized), 350);
    return () => clearTimeout(timer);
  }, [normalized, templates.length, refreshPreview]);

  const setEnvSpec = (nextSpec) => {
    onRunParamsDefaultsChange({
      ...normalized,
      env_spec: nextSpec,
    });
  };

  const onTemplateChange = (tid) => {
    const tpl = templatesById[tid];
    setEnvSpec(normalizeEnvSpec({
      kind: 'template',
      template_id: tid,
      inputs: tpl ? defaultInputsForTemplate(tpl) : {},
    }, templatesById));
  };

  const scriptText = envSpec.script_override || activeTemplate?.script || '';

  return (
    <section className="compose-global-run-panel platform-surface-card">
      <div className="compose-global-run-head">
        <div>
          <h3 className="compose-global-run-title">运行参数</h3>
          <p className="muted compose-global-run-hint">
            每次运行前自动计算并注入查询步骤（如时间范围）。
          </p>
        </div>
        <label className="compose-run-name">
          <span>时间模板</span>
          <select
            className="form-select"
            value={templateId}
            onChange={(e) => onTemplateChange(e.target.value)}
          >
            {templates.map((t) => (
              <option key={t.id} value={t.id}>{t.label}</option>
            ))}
            {!templates.length && <option value="time_preset">快捷时段</option>}
          </select>
        </label>
      </div>

      {activeTemplate?.description && (
        <p className="muted compose-global-run-template-desc">{activeTemplate.description}</p>
      )}

      <RunEnvTemplateFields
        schema={activeTemplate?.param_schema}
        inputs={envSpec.inputs || {}}
        onChange={(inputs) => setEnvSpec({ ...envSpec, inputs })}
      />

      <details className="compose-run-advanced">
        <summary>高级选项（脚本与预览）</summary>
        {scriptText && (
          <details className="run-env-script-details">
            <summary>计算脚本（只读）</summary>
            <pre className="run-env-script-pre">{scriptText}</pre>
          </details>
        )}

        <div className="run-env-preview-block">
          <span className="run-env-preview-label">
            参数预览
            {loadingPreview && <span className="muted"> · 计算中…</span>}
          </span>
          {previewError && <p className="run-env-preview-error">{previewError}</p>}
          {!previewError && (
            <ul className="run-env-preview-list">
              {Object.entries(previewEnv).map(([k, v]) => (
                <li key={k}><code>{k}</code> = {v}</li>
              ))}
              {!Object.keys(previewEnv).length && !loadingPreview && (
                <li className="muted">（无输出）</li>
              )}
            </ul>
          )}
        </div>
      </details>

      <GlobalEnvEditor
        rows={extraEnvRows}
        hint="额外固定参数（可选）；与上方计算结果同名时优先使用。"
        onChange={(idx, field, value) => {
          onExtraEnvRowsChange(patchGlobalEnvRows(extraEnvRows, idx, field, value));
        }}
      />
    </section>
  );
}
