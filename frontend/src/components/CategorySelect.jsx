import { useEffect, useRef, useState } from 'react';

export function CategorySelect({ options, selected, onChange, placeholder = '选择缺陷类别…' }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const sel = new Set(selected || []);
  const filtered = (options || []).filter((c) => !query || c.includes(query));

  const toggle = (cat) => {
    const next = new Set(sel);
    if (next.has(cat)) next.delete(cat);
    else next.add(cat);
    onChange([...next]);
  };

  const selectAll = () => onChange([...(options || [])]);
  const clearAll = () => onChange([]);

  return (
    <div className={`rt-select${open ? ' is-open' : ''}`} ref={rootRef}>
      <div className="rt-trigger" onClick={() => setOpen(!open)} role="button" tabIndex={0} onKeyDown={(e) => e.key === 'Enter' && setOpen(!open)}>
        {sel.size
          ? [...sel].map((c) => (
            <span key={c} className="rt-tag">
              {c}
              <button type="button" className="rt-tag-x" onClick={(e) => { e.stopPropagation(); toggle(c); }} aria-label={`移除 ${c}`}>×</button>
            </span>
          ))
          : <span className="rt-placeholder rt-placeholder-warn">{placeholder}</span>}
      </div>
      {open && (
        <div className="rt-dropdown">
          <input
            className="rt-search"
            placeholder="搜索类别…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onClick={(e) => e.stopPropagation()}
          />
          <div className="rt-dropdown-actions">
            <button type="button" className="btn btn-sm btn-ghost" onClick={selectAll}>全选</button>
            <button type="button" className="btn btn-sm btn-ghost" onClick={clearAll}>清空</button>
          </div>
          <div className="rt-options">
            {filtered.map((c) => (
              <label key={c} className="rt-option">
                <input type="checkbox" checked={sel.has(c)} onChange={() => toggle(c)} />
                <span>{c}</span>
              </label>
            ))}
            {!filtered.length && <span className="rt-placeholder">无匹配类别</span>}
          </div>
        </div>
      )}
    </div>
  );
}
