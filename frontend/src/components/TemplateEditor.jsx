import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';

const FIELD_TYPES = [
  { value: 'text', label: '文本' },
  { value: 'number', label: '数字' },
  { value: 'select', label: '单选' },
  { value: 'multiselect', label: '多选' },
  { value: 'boolean', label: '开关' },
];

function defaultField() {
  return { key: '', label: '', type: 'text', default: '' };
}

function formatPreviewValue(field, value) {
  if (field.type === 'boolean') return value ? '是' : '否';
  if (Array.isArray(value)) return value.length ? value.join('、') : '未配置';
  if (value === '' || value == null) return '—';
  return String(value);
}

function ParamFieldInput({ field, value, onChange, categoryOptions }) {
  const opts = field.key === 'categories' && categoryOptions.length
    ? categoryOptions
    : (field.options || []);

  if (field.type === 'number') {
    return (
      <input
        type="number"
        className="form-input"
        min={field.min}
        max={field.max}
        step={field.step || 0.05}
        value={value ?? field.default ?? 0}
        onChange={(e) => onChange(+e.target.value)}
      />
    );
  }
  if (field.type === 'boolean') {
    return (
      <label className="rb-toggle">
        <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
        <span>{value ? '开启' : '关闭'}</span>
      </label>
    );
  }
  if (field.type === 'select') {
    const selectOpts = opts.map((o) => (typeof o === 'object' ? o : { value: o, label: o }));
    return (
      <select className="form-select" value={value ?? field.default ?? ''} onChange={(e) => onChange(e.target.value)}>
        {selectOpts.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    );
  }
  if (field.type === 'multiselect') {
    const selected = new Set(Array.isArray(value) ? value : []);
    return (
      <div className="template-multiselect">
        {opts.slice(0, 24).map((o) => {
          const v = typeof o === 'object' ? o.value : o;
          const label = typeof o === 'object' ? o.label : o;
          return (
            <label key={v} className="template-ms-item">
              <input
                type="checkbox"
                checked={selected.has(v)}
                onChange={() => {
                  const next = new Set(selected);
                  if (next.has(v)) next.delete(v); else next.add(v);
                  onChange([...next]);
                }}
              />
              <span>{label}</span>
            </label>
          );
        })}
        {opts.length > 24 && <span className="muted">…共 {opts.length} 项</span>}
      </div>
    );
  }
  return (
    <input
      type="text"
      className="form-input"
      value={value ?? field.default ?? ''}
      onChange={(e) => onChange(e.target.value)}
    />
  );
}

export function TemplateEditor({ draft, onChange }) {
  const schema = draft.params_schema || [];
  const [previewParams, setPreviewParams] = useState({});
  const [categoryOptions, setCategoryOptions] = useState([]);

  useEffect(() => {
    api.getDefectCategories().then((res) => {
      if (res.success) setCategoryOptions(res.categories || []);
    });
  }, []);

  useEffect(() => {
    const defaults = {};
    schema.forEach((f) => {
      defaults[f.key] = f.default ?? (f.type === 'multiselect' ? [] : f.type === 'boolean' ? false : '');
    });
    setPreviewParams(defaults);
  }, [draft.id, JSON.stringify(schema.map((f) => [f.key, f.type, f.default]))]);

  const previewSummary = useMemo(
    () => schema.slice(0, 3).map((f) => [f.label, formatPreviewValue(f, previewParams[f.key])]),
    [schema, previewParams],
  );

  const updateSchema = (next) => onChange({ ...draft, params_schema: next });

  const updateField = (i, patch) => {
    updateSchema(schema.map((f, idx) => (idx === i ? { ...f, ...patch } : f)));
  };

  const addField = () => updateSchema([...schema, defaultField()]);

  const removeField = (i) => updateSchema(schema.filter((_, idx) => idx !== i));

  const moveField = (i, dir) => {
    const j = i + dir;
    if (j < 0 || j >= schema.length) return;
    const next = [...schema];
    [next[i], next[j]] = [next[j], next[i]];
    updateSchema(next);
  };

  return (
    <div className="template-editor">
      <div className="form-row">
        <div className="form-group">
          <label>名称</label>
          <input className="form-input" value={draft.name || ''} onChange={(e) => onChange({ ...draft, name: e.target.value })} />
        </div>
        <div className="form-group">
          <label>图标</label>
          <input className="form-input" value={draft.icon || ''} onChange={(e) => onChange({ ...draft, icon: e.target.value })} placeholder="filter / target / code" />
        </div>
      </div>
      <div className="form-group">
        <label>描述</label>
        <input className="form-input" value={draft.description || ''} onChange={(e) => onChange({ ...draft, description: e.target.value })} />
      </div>

      <div className="template-preview-row">
        <div className="pipeline-flow template-block-preview">
          <div className="flow-node-wrapper">
            <div className="flow-node">
              <div className="flow-node-icon">◆</div>
              <div className="flow-node-body">
                <div className="flow-node-name">{draft.name || draft.id || '块模板'}</div>
                <div className="flow-node-params">
                  {previewSummary.length
                    ? previewSummary.map(([k, v]) => `${k}: ${v}`).join(' · ')
                    : (draft.description || '无参数')}
                </div>
              </div>
            </div>
          </div>
        </div>
        <div className="block-params visible template-param-preview">
          <h4>参数预览</h4>
          {!schema.length ? (
            <p className="muted">此模板无参数字段</p>
          ) : schema.map((f) => (
            <div key={f.key || f.label} className="form-group">
              <label>{f.label || f.key}</label>
              <ParamFieldInput
                field={f}
                value={previewParams[f.key]}
                categoryOptions={categoryOptions}
                onChange={(v) => setPreviewParams((p) => ({ ...p, [f.key]: v }))}
              />
            </div>
          ))}
        </div>
      </div>

      <details open className="code-section">
        <summary>参数字段 schema</summary>
        <div className="template-schema-editor">
          {schema.map((f, i) => (
            <div key={i} className="template-schema-row">
              <div className="template-schema-actions">
                <button type="button" className="btn btn-sm btn-ghost" disabled={i === 0} onClick={() => moveField(i, -1)}>↑</button>
                <button type="button" className="btn btn-sm btn-ghost" disabled={i === schema.length - 1} onClick={() => moveField(i, 1)}>↓</button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => removeField(i)}>×</button>
              </div>
              <input className="form-input" placeholder="key" value={f.key || ''} onChange={(e) => updateField(i, { key: e.target.value })} />
              <input className="form-input" placeholder="标签" value={f.label || ''} onChange={(e) => updateField(i, { label: e.target.value })} />
              <select className="form-select" value={f.type || 'text'} onChange={(e) => updateField(i, { type: e.target.value })}>
                {FIELD_TYPES.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}
              </select>
              {(f.type === 'select' || f.type === 'multiselect') && (
                <textarea
                  className="form-textarea"
                  placeholder="选项，逗号分隔"
                  value={(f.options || []).map((o) => (typeof o === 'object' ? o.value : o)).join(', ')}
                  onChange={(e) => updateField(i, {
                    options: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  })}
                />
              )}
              {f.type === 'number' && (
                <div className="form-row template-number-meta">
                  <input type="number" className="form-input" placeholder="min" value={f.min ?? ''} onChange={(e) => updateField(i, { min: +e.target.value })} />
                  <input type="number" className="form-input" placeholder="max" value={f.max ?? ''} onChange={(e) => updateField(i, { max: +e.target.value })} />
                  <input type="number" className="form-input" placeholder="step" value={f.step ?? ''} onChange={(e) => updateField(i, { step: +e.target.value })} />
                </div>
              )}
            </div>
          ))}
          <button type="button" className="btn-add-block" onClick={addField}>+ 添加参数字段</button>
        </div>
      </details>

      <div className="form-group">
        <label>Python 代码</label>
        <textarea className="form-textarea code-area-tall" value={draft.python_code || ''} onChange={(e) => onChange({ ...draft, python_code: e.target.value })} />
      </div>
    </div>
  );
}
