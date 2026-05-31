import { useEffect, useMemo, useRef, useState } from 'react';

/** 单框：可输入，也可点 ▾ 展开下拉选择 */
export function FilterCombo({
  value,
  onChange,
  placeholder,
  options = [],
  className = '',
  type = 'text',
  title,
  min,
  max,
  step,
}) {
  const rootRef = useRef(null);
  const inputRef = useRef(null);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const displayValue = value ?? '';
  const hasOptions = options.length > 0;

  const filtered = useMemo(() => {
    if (!hasOptions) return [];
    const q = (open ? query : displayValue).trim().toLowerCase();
    if (!q) return options;
    return options.filter((o) => String(o).toLowerCase().includes(q));
  }, [options, query, displayValue, open, hasOptions]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const openMenu = () => {
    if (!hasOptions) return;
    setQuery(displayValue);
    setOpen(true);
  };

  const pick = (opt) => {
    onChange(opt);
    setQuery('');
    setOpen(false);
    inputRef.current?.blur();
  };

  const onInputChange = (e) => {
    const v = e.target.value;
    onChange(v);
    setQuery(v);
    if (hasOptions) setOpen(true);
  };

  const onKeyDown = (e) => {
    if (e.key === 'Escape') {
      setOpen(false);
      return;
    }
    if (e.key === 'ArrowDown' && hasOptions) {
      e.preventDefault();
      openMenu();
    }
  };

  return (
    <div
      className={`filter-combo${open ? ' is-open' : ''}${className ? ` ${className}` : ''}`}
      ref={rootRef}
    >
      <input
        ref={inputRef}
        type={type}
        className="filter-combo-input result-filter-combo"
        placeholder={placeholder}
        title={title || placeholder}
        value={displayValue}
        onChange={onInputChange}
        onFocus={() => { if (hasOptions) { setQuery(displayValue); setOpen(true); } }}
        onKeyDown={onKeyDown}
        min={min}
        max={max}
        step={step}
      />
      {hasOptions && (
        <button
          type="button"
          className="filter-combo-toggle"
          tabIndex={-1}
          aria-label={`${placeholder} 下拉`}
          onMouseDown={(e) => {
            e.preventDefault();
            if (open) setOpen(false);
            else {
              inputRef.current?.focus();
              openMenu();
            }
          }}
        >
          ▾
        </button>
      )}
      {open && hasOptions && (
        <div className="filter-combo-menu" role="listbox">
          {filtered.length === 0 ? (
            <div className="filter-combo-empty">无匹配项</div>
          ) : (
            filtered.map((opt) => (
              <button
                key={opt}
                type="button"
                className={`filter-combo-option${opt === displayValue ? ' is-active' : ''}`}
                role="option"
                aria-selected={opt === displayValue}
                onMouseDown={(e) => {
                  e.preventDefault();
                  pick(opt);
                }}
              >
                {opt}
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}

export function statusInputValue(status) {
  if (status === '1') return 'NG';
  if (status === '0') return 'OK';
  return status || '';
}

export function parseStatusInput(text) {
  const t = String(text || '').trim();
  if (!t) return '';
  if (t === '1' || /^ng$/i.test(t)) return '1';
  if (t === '0' || /^ok$/i.test(t)) return '0';
  return t;
}
