import {
  QUERY_COMPACT_HIDE_DEFS,
  defaultCompactHideMap,
} from '../../lib/queryCompactHide';

export default function QueryCompactHideEditor({ value, onChange, disabled }) {
  const map = { ...defaultCompactHideMap(), ...(value || {}) };

  const toggle = (key, checked) => {
    onChange({ ...map, [key]: checked });
  };

  return (
    <div className="query-compact-hide-editor">
      <p className="muted strategy-panel-hint">
        仅在查询页为「简洁」视图时生效：勾选的区块将对操作员隐藏。筛选规则默认显示（仅规则表，不可切代码）。
      </p>
      <div className="query-compact-hide-grid">
        {QUERY_COMPACT_HIDE_DEFS.map(({ key, label }) => (
          <label key={key} className="query-compact-hide-check">
            <input
              type="checkbox"
              checked={!!map[key]}
              disabled={disabled}
              onChange={(e) => toggle(key, e.target.checked)}
            />
            <span>隐藏 {label}</span>
          </label>
        ))}
      </div>
    </div>
  );
}
