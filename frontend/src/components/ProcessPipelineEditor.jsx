import { useCallback, useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import {
  defaultPipelineFromPresets,
  ensureProcessPipeline,
  moveStep,
  newPipelineStepId,
  normalizePipelineStep,
  normalizeProcessPipeline,
  presetGroupsFromPipeline,
} from '../lib/processPipeline';

function StepParamsForm({ step, template, onChange }) {
  const schema = template?.params_schema || [];
  if (!schema.length) {
    return <p className="muted pipeline-step-empty-params">此步骤无可调参数</p>;
  }
  return (
    <div className="pipeline-step-params">
      {schema.map((field) => {
        const key = field.key;
        const val = step.params?.[key] ?? field.default ?? '';
        const options = field.options || [];
        if (field.type === 'select' || (options.length > 0 && field.type !== 'multiselect')) {
          return (
            <label key={key} className="pipeline-param-row">
              <span>{field.label || key}</span>
              <select
                className="form-select"
                value={String(val)}
                onChange={(e) => onChange({ ...step.params, [key]: e.target.value })}
              >
                {options.map((o) => (
                  <option key={o.value} value={o.value}>{o.label}</option>
                ))}
              </select>
            </label>
          );
        }
        return (
          <label key={key} className="pipeline-param-row">
            <span>{field.label || key}</span>
            <input
              className="form-input"
              type={field.type === 'number' ? 'number' : 'text'}
              value={val}
              onChange={(e) => onChange({ ...step.params, [key]: e.target.value })}
            />
          </label>
        );
      })}
    </div>
  );
}

/**
 * process_data 调用链：按顺序加载块模板步骤，顺序即 process_data 中的执行顺序。
 */
export default function ProcessPipelineEditor({ draft, onChange, templatesMap = {} }) {
  const [catalog, setCatalog] = useState([]);
  const [preview, setPreview] = useState('');
  const [previewErr, setPreviewErr] = useState('');
  const [addTpl, setAddTpl] = useState('');

  useEffect(() => {
    api.getPipelineTemplates()
      .then((r) => setCatalog(r.data || []))
      .catch(() => setCatalog([]));
  }, []);

  const pipeline = useMemo(
    () => ensureProcessPipeline(draft, templatesMap),
    [draft, templatesMap],
  );

  const refreshPreview = useCallback((pipe) => {
    const body = { process_pipeline: pipe };
    api.compileProcessPipeline(body)
      .then((r) => {
        if (r.data?.valid) {
          setPreview(r.data.python_code || '');
          setPreviewErr('');
        } else {
          setPreview('');
          setPreviewErr((r.data?.errors || []).join('; ') || r.error || '编译失败');
        }
      })
      .catch((e) => {
        setPreview('');
        setPreviewErr(e.message || '编译失败');
      });
  }, []);

  useEffect(() => {
    if (pipeline.length) refreshPreview(pipeline);
    else {
      setPreview('');
      setPreviewErr('');
    }
  }, [pipeline, refreshPreview]);

  const patchPipeline = (nextPipe, extra = {}) => {
    const normalized = normalizeProcessPipeline(nextPipe, templatesMap);
    const groups = presetGroupsFromPipeline(normalized, templatesMap);
    onChange({
      ...draft,
      ...extra,
      process_pipeline: normalized,
      python_presets: groups,
    });
  };

  const applyPipelineToCode = () => {
    if (!pipeline.length) return;
    api.compileProcessPipeline({ process_pipeline: pipeline })
      .then((r) => {
        if (!r.data?.valid) {
          setPreviewErr((r.data?.errors || []).join('; ') || '编译失败');
          return;
        }
        onChange({
          ...draft,
          python_code: r.data.python_code || '',
          python_code_manual: false,
        });
      })
      .catch((e) => setPreviewErr(e.message || '编译失败'));
  };

  const updateStep = (idx, patch) => {
    const next = pipeline.map((s, i) => (i === idx ? normalizePipelineStep({ ...s, ...patch }, templatesMap) : s));
    patchPipeline(next);
  };

  const removeStep = (idx) => patchPipeline(pipeline.filter((_, i) => i !== idx));

  const addStep = () => {
    if (!addTpl) return;
    const tpl = templatesMap[addTpl] || catalog.find((t) => t.id === addTpl);
    const defaults = {};
    (tpl?.params_schema || []).forEach((f) => {
      if (f.default != null && f.default !== '') defaults[f.key] = f.default;
    });
    patchPipeline([
      ...pipeline,
      normalizePipelineStep({ id: newPipelineStepId(), template_id: addTpl, params: defaults }, templatesMap),
    ]);
    setAddTpl('');
  };

  const applyPresetBundle = (presetIds) => {
    patchPipeline(defaultPipelineFromPresets(presetIds));
  };

  return (
    <div className="process-pipeline-editor">
      <div className="process-pipeline-head">
        <div>
          <h3 className="strategy-env-schema-title">process_data 调用链</h3>
          <p className="strategy-panel-hint muted">
            从上到下即 <code>process_data</code> 中的执行顺序。预设三步（观察 / 筛选 / 采样）已做成块模板，也可插入其它带
            <code>process_lines</code> 或 <code>python_code</code> 的块模板。
          </p>
        </div>
        <div className="process-pipeline-quick-bundles">
          <span className="muted">快捷：</span>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => applyPresetBundle(['observe', 'filter'])}>观察+筛选</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => applyPresetBundle(['observe', 'filter', 'sampling'])}>全流程</button>
        </div>
      </div>

      <ol className="process-pipeline-list">
        {pipeline.map((step, idx) => {
          const tpl = { ...catalog.find((t) => t.id === step.template_id), ...templatesMap[step.template_id] };
          const title = tpl?.name || step.template_id;
          const group = tpl?.preset_group;
          return (
            <li key={step.id} className="process-pipeline-item">
              <div className="process-pipeline-item-head">
                <span className="process-pipeline-order">{idx + 1}</span>
                <span className="process-pipeline-title">{title}</span>
                {group && <span className="strategy-pill strategy-pill-muted">{group}</span>}
                <code className="process-pipeline-tpl-id">{step.template_id}</code>
                <div className="process-pipeline-item-actions">
                  <button type="button" className="btn btn-sm btn-ghost" disabled={idx === 0} onClick={() => patchPipeline(moveStep(pipeline, idx, -1))}>↑</button>
                  <button type="button" className="btn btn-sm btn-ghost" disabled={idx === pipeline.length - 1} onClick={() => patchPipeline(moveStep(pipeline, idx, 1))}>↓</button>
                  <button type="button" className="btn btn-sm btn-ghost strategy-action-danger" onClick={() => removeStep(idx)}>删除</button>
                </div>
              </div>
              <StepParamsForm
                step={step}
                template={tpl}
                onChange={(params) => updateStep(idx, { params })}
              />
            </li>
          );
        })}
      </ol>

      {pipeline.length === 0 && (
        <p className="muted process-pipeline-empty">尚未配置步骤。请从下方添加块模板，或使用快捷组合。</p>
      )}

      <div className="process-pipeline-add">
        <select className="form-select" value={addTpl} onChange={(e) => setAddTpl(e.target.value)}>
          <option value="">添加块模板步骤…</option>
          {catalog.map((t) => (
            <option key={t.id} value={t.id}>{t.category ? `[${t.category}] ` : ''}{t.name} ({t.id})</option>
          ))}
        </select>
        <button type="button" className="btn btn-sm btn-primary" disabled={!addTpl} onClick={addStep}>添加</button>
      </div>

      <div className="process-pipeline-preview">
        <div className="process-pipeline-preview-head">
          <h4 className="process-pipeline-preview-title">调用链编译预览</h4>
          <button
            type="button"
            className="btn btn-sm btn-secondary"
            disabled={!pipeline.length}
            onClick={applyPipelineToCode}
          >
            应用调用链到代码
          </button>
        </div>
        {previewErr && <p className="strategy-panel-hint strategy-panel-warn">{previewErr}</p>}
        <textarea className="form-textarea code-area" readOnly rows={8} value={preview || '# 添加步骤后预览…'} />
        <p className="strategy-panel-hint muted">
          修改下方手写代码会自动保留；仅点击「应用调用链到代码」时才用调用链覆盖。
        </p>
      </div>
    </div>
  );
}
