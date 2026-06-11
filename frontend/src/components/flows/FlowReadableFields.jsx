/** 表单化展示节点入参/出参（非 YAML/JSON 原文） */
export default function FlowReadableFields({ fields = [], mode = 'design', variant = 'in' }) {
  if (!fields.length) {
    return <p className="flows-muted">暂无{variant === 'in' ? '入参' : '出参'}说明</p>;
  }

  return (
    <dl className="flows-param-form">
      {fields.map((field) => (
        <div key={field.key} className="flows-param-row">
          <dt className="flows-param-label">
            <span className="flows-param-title">{field.title || field.key}</span>
            <code className="flows-param-key">{field.key}</code>
          </dt>
          <dd className="flows-param-body">
            {field.description && (
              <p className="flows-param-desc">{field.description}</p>
            )}
            {variant === 'in' && (
              <div className="flows-param-value-block">
                <span className="flows-param-value-label">配置值</span>
                <span className="flows-param-value">{field.value || '—'}</span>
              </div>
            )}
            {mode === 'run' && field.actual_display != null && (
              <div className="flows-param-value-block flows-param-value-block--actual">
                <span className="flows-param-value-label">实际值</span>
                <span className="flows-param-value">{field.actual_display}</span>
              </div>
            )}
            {variant === 'out' && field.used_by && (
              <div className="flows-param-meta">
                传递给：
                {field.used_by}
              </div>
            )}
            {variant === 'out' && mode !== 'run' && !field.used_by && field.description && (
              <div className="flows-param-meta flows-param-meta--muted">运行后由工具产出</div>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}
