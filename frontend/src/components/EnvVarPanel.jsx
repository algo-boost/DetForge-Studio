import { SYSTEM_VAR_HINTS } from '../lib/envVars';

function FieldInput({ field, value, onChange }) {
  const type = field.type === 'number' ? 'number' : 'text';
  return (
    <label className="env-var-field">
      <span className="env-var-label">
        {field.label || field.key}
        <code className="env-var-key">${'${'}{field.key}{'}'}</code>
      </span>
      <input
        type={type}
        step={type === 'number' ? '0.01' : undefined}
        placeholder={field.placeholder || field.description || ''}
        value={value ?? ''}
        onChange={(e) => onChange(field.key, e.target.value)}
        data-testid={`env-var-${field.key}`}
      />
      {field.description && <span className="muted env-var-desc">{field.description}</span>}
    </label>
  );
}

export default function EnvVarPanel({
  title,
  schema = [],
  values = {},
  onChange,
  systemPreview = {},
  testId,
  emptyHint = '该策略未声明自定义变量，可在下方「全局环境变量」中手动添加。',
}) {
  const hasSystem = Object.keys(systemPreview || {}).length > 0;

  return (
    <section className="env-var-panel" data-testid={testId}>
      {title && <h4 className="env-var-panel-title">{title}</h4>}
      {schema.length > 0 ? (
        <div className="env-var-grid">
          {schema.map((field) => (
            <FieldInput
              key={field.key}
              field={field}
              value={values[field.key] ?? ''}
              onChange={onChange}
            />
          ))}
        </div>
      ) : (
        <p className="muted env-var-empty">{emptyHint}</p>
      )}
      {hasSystem && (
        <details className="env-var-system" open={schema.length === 0}>
          <summary>系统自动注入变量（只读预览）</summary>
          <ul className="env-var-system-list">
            {Object.entries(systemPreview).map(([key, val]) => (
              <li key={key}>
                <code>{'${'}{key}{'}'}</code>
                <span>{val}</span>
                {SYSTEM_VAR_HINTS[key] && <em className="muted">{SYSTEM_VAR_HINTS[key]}</em>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}

export function GlobalEnvEditor({ rows = [], onChange }) {
  return (
    <section className="env-var-panel env-var-global" data-testid="env-var-global">
      <h3 className="env-var-panel-title">全局环境变量</h3>
      <p className="muted env-var-global-hint">Stage1 / Stage2 策略均可引用；键名建议使用大写，如 PRODUCT_LINE。</p>
      <div className="env-var-kv-list">
        {rows.map((row, idx) => (
          <div key={row._id || idx} className="env-var-kv-row">
            <input
              placeholder="KEY"
              value={row.key}
              onChange={(e) => onChange(idx, 'key', e.target.value.toUpperCase())}
            />
            <input
              placeholder="值"
              value={row.value}
              onChange={(e) => onChange(idx, 'value', e.target.value)}
            />
            <button type="button" className="btn btn-sm btn-ghost" onClick={() => onChange(idx, '__delete')}>删除</button>
          </div>
        ))}
      </div>
      <button
        type="button"
        className="btn btn-sm btn-ghost"
        onClick={() => onChange(rows.length, '__add')}
      >
        + 添加变量
      </button>
    </section>
  );
}
