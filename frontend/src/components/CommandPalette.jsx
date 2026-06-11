import { useEffect, useRef } from 'react';
import { PRODUCT_NAME } from '../config/brand';

export default function CommandPalette({
  open,
  query,
  setQuery,
  activeIndex,
  setActiveIndex,
  filtered,
  closePalette,
  runCommand,
}) {
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 0);
      return () => clearTimeout(t);
    }
    return undefined;
  }, [open]);

  if (!open) return null;

  const grouped = filtered.reduce((acc, cmd) => {
    const g = cmd.group || '其他';
    if (!acc[g]) acc[g] = [];
    acc[g].push(cmd);
    return acc;
  }, {});

  let flatIndex = 0;

  return (
    <div
      className="cmd-palette-backdrop"
      role="presentation"
      onClick={closePalette}
    >
      <div
        className="cmd-palette"
        role="dialog"
        aria-modal="true"
        aria-label="命令面板"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cmd-palette-input-row">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            ref={inputRef}
            type="search"
            className="cmd-palette-input"
            placeholder={`搜索 ${PRODUCT_NAME} 页面与操作…`}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            aria-label="搜索命令"
            autoComplete="off"
          />
          <kbd className="cmd-palette-kbd">Esc</kbd>
        </div>
        <div className="cmd-palette-list" role="listbox">
          {filtered.length === 0 && (
            <div className="cmd-palette-empty">无匹配命令</div>
          )}
          {Object.entries(grouped).map(([group, items]) => (
            <div key={group} className="cmd-palette-group">
              <div className="cmd-palette-group-label">{group}</div>
              {items.map((cmd) => {
                const idx = flatIndex;
                flatIndex += 1;
                const active = idx === activeIndex;
                return (
                  <button
                    key={cmd.id}
                    type="button"
                    role="option"
                    aria-selected={active}
                    className={`cmd-palette-item${active ? ' is-active' : ''}`}
                    onMouseEnter={() => setActiveIndex(idx)}
                    onClick={() => runCommand(cmd)}
                  >
                    <span>{cmd.label}</span>
                    {cmd.action.type === 'navigate' && (
                      <span className="cmd-palette-item-meta">{cmd.action.path}</span>
                    )}
                  </button>
                );
              })}
            </div>
          ))}
        </div>
        <div className="cmd-palette-footer">
          <span><kbd>↑↓</kbd> 选择</span>
          <span><kbd>↵</kbd> 执行</span>
          <span><kbd>⌘K</kbd> 关闭</span>
        </div>
      </div>
    </div>
  );
}
