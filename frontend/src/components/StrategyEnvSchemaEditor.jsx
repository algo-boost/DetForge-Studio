import { inferEnvSchemaFromTexts, mergeEnvSchema, newEnvSchemaRow, RUNTIME_SYSTEM_VARS, RUNTIME_VAR_HINT } from '../lib/envVars';

const RESERVED_KEYS = RUNTIME_SYSTEM_VARS;

export default function StrategyEnvSchemaEditor({ draft, onChange }) {
  const schema = draft?.env_schema || [];

  const updateRow = (idx, patch) => {
    const key = String(patch.key ?? schema[idx]?.key ?? '').toUpperCase();
    if (patch.key != null && RESERVED_KEYS.has(key)) return;
    const next = schema.map((row, i) => (
      i === idx ? { ...row, ...patch, key: key || row.key } : row
    ));
    onChange({ ...draft, env_schema: next });
  };

  const addRow = () => onChange({ ...draft, env_schema: [...schema, newEnvSchemaRow()] });

  const removeRow = (idx) => onChange({
    ...draft,
    env_schema: schema.filter((_, i) => i !== idx),
  });

  const inferFromCode = () => {
    const inferred = inferEnvSchemaFromTexts(
      draft?.sql_template,
      draft?.python_code,
      draft?.filter_rules_code,
      draft?.sample_code,
    );
    onChange({ ...draft, env_schema: mergeEnvSchema(schema, inferred) });
  };

  return (
    <div className="strategy-env-schema-editor">
      <div className="strategy-env-schema-head">
        <div>
          <h3 className="strategy-env-schema-title">可调参数</h3>
          <p className="strategy-panel-hint">
            自定义参数：SQL 写
            {' '}
            <code>{'${NUM}'}</code>
            ，Python 写
            {' '}
            <code>get_env('NUM')</code>
            。KEY 须大写字母开头，仅含 A-Z、0-9、_。
          </p>
          <p className="muted strategy-env-schema-reserved">
            时段用工具栏；下列为运行时自动注入，勿重复定义：
            {' '}
            {RUNTIME_VAR_HINT}
          </p>
        </div>
        <div className="strategy-env-schema-actions">
          <button type="button" className="btn btn-sm btn-ghost" onClick={inferFromCode}>
            从 SQL/Python 推断
          </button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={addRow}>
            + 添加参数
          </button>
        </div>
      </div>

      {schema.length === 0 ? (
        <p className="muted strategy-env-schema-empty">
          暂无自定义参数。若 SQL/Python 中有
          {' '}
          <code>{'${NUM}'}</code>
          {' '}
          等占位符，点「从 SQL/Python 推断」自动填充；也可手动添加并填写中文名。
        </p>
      ) : (
        <div className="strategy-env-schema-table">
          <div className="strategy-env-schema-row strategy-env-schema-header">
            <span>变量 KEY</span>
            <span>中文名</span>
            <span>类型</span>
            <span>默认值</span>
            <span>说明</span>
            <span />
          </div>
          {schema.map((row, idx) => (
            <div key={`${row.key}-${idx}`} className="strategy-env-schema-row">
              <input
                value={row.key || ''}
                placeholder="NUM"
                onChange={(e) => updateRow(idx, { key: e.target.value.toUpperCase() })}
              />
              <input
                value={row.label || ''}
                placeholder="图片数量"
                onChange={(e) => updateRow(idx, { label: e.target.value })}
              />
              <select value={row.type || 'text'} onChange={(e) => updateRow(idx, { type: e.target.value })}>
                <option value="text">文本</option>
                <option value="number">数字</option>
              </select>
              <input
                value={row.default ?? ''}
                placeholder="默认"
                onChange={(e) => updateRow(idx, { default: e.target.value })}
              />
              <input
                value={row.description || ''}
                placeholder="可选"
                onChange={(e) => updateRow(idx, { description: e.target.value })}
              />
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => removeRow(idx)}>删</button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
