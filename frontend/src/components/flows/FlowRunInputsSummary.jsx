/** 展示本次运行 inputs（表单风格，非 JSON） */
export default function FlowRunInputsSummary({ inputs = {}, schema = {} }) {
  const entries = Object.entries(inputs || {});
  if (!entries.length) return null;

  return (
    <dl className="flows-param-form flows-run-inputs-summary">
      {entries.map(([key, val]) => {
        const spec = schema[key] || {};
        const label = spec.label || key;
        const display = typeof val === 'object' ? JSON.stringify(val) : String(val ?? '—');
        return (
          <div key={key} className="flows-param-row">
            <dt className="flows-param-label">
              <span className="flows-param-title">{label}</span>
              <code className="flows-param-key">{key}</code>
            </dt>
            <dd className="flows-param-body">
              <div className="flows-param-value-block flows-param-value-block--actual">
                <span className="flows-param-value-label">本次值</span>
                <span className="flows-param-value">{display}</span>
              </div>
            </dd>
          </div>
        );
      })}
    </dl>
  );
}
