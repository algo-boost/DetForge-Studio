import { useEffect, useMemo, useRef, useState } from 'react';
import { api, toast } from '../api/client';

export function StrategyPicker({
  strategies, value, onSelect, onImportClick, onDeleteRequest,
}) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);

  const current = strategies.find((s) => s.id === value);

  const sorted = useMemo(() => {
    return [...strategies].sort((a, b) => {
      const ca = a.category || '';
      const cb = b.category || '';
      if (ca !== cb) return ca.localeCompare(cb, 'zh-CN');
      return (a.name || a.id || '').localeCompare(b.name || b.id || '', 'zh-CN');
    });
  }, [strategies]);

  useEffect(() => {
    if (!open) return undefined;
    const onDoc = (e) => {
      if (!rootRef.current?.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, [open]);

  const exportById = async (id, e) => {
    e?.stopPropagation();
    try {
      const res = await api.getStrategy(id);
      if (!res.success) throw new Error(res.error);
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `${id}.json`;
      a.click();
      toast('已导出');
    } catch (err) { toast(err.message, 'error'); }
  };

  const pick = (id) => {
    onSelect(id);
    setOpen(false);
  };

  const renderRow = (s) => (
    <div key={s.id} className="strategy-menu-row">
      <button type="button" className={`strategy-menu-item${value === s.id ? ' active' : ''}`} onClick={() => pick(s.id)}>
        <span className="smi-name">{s.name}</span>
        <span className="smi-desc">{s.description || s.category || s.id}</span>
      </button>
      <div className="strategy-menu-actions">
        <button type="button" className="strategy-menu-export" title="导出 JSON" onClick={(e) => exportById(s.id, e)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3" /></svg>
        </button>
        {onDeleteRequest && (
          <button type="button" className="strategy-menu-delete" title="删除" onClick={(e) => { e.stopPropagation(); onDeleteRequest(s.id); setOpen(false); }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></svg>
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="strategy-picker" ref={rootRef}>
      <button type="button" className="strategy-picker-btn" onClick={() => setOpen(!open)}>
        <span id="strategy-picker-label">{current ? current.name : '自由查询'}</span>
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div className="strategy-menu">
          <button type="button" className={`strategy-menu-item${!value ? ' active' : ''}`} onClick={() => pick('')}>
            <span className="smi-name">自由查询</span>
            <span className="smi-desc">SQL + 规则 / 代码</span>
          </button>
          {sorted.length > 0 && (
            <>
              <div className="strategy-menu-divider">策略</div>
              {sorted.map(renderRow)}
            </>
          )}
          <div className="strategy-menu-divider">操作</div>
          <button type="button" className="strategy-menu-item strategy-menu-import" onClick={() => { onImportClick?.(); setOpen(false); }}>
            <span className="smi-name">导入 JSON…</span>
            <span className="smi-desc">从文件恢复策略</span>
          </button>
        </div>
      )}
    </div>
  );
}
