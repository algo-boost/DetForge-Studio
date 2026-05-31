import { useCallback, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { toast } from '../api/client';
import { Modal } from '../components/Modal';
import SceneHubNav from '../components/SceneHubNav';
import { clearHistory, loadHistory } from '../lib/history';
import {
  applyHistoryFilters,
  countByStrategy,
  DEFAULT_HISTORY_FILTERS,
  groupHistoryByStrategy,
  hasActiveFilters,
  HISTORY_TIME_PRESETS,
  strategyColor,
  uniqueStrategies,
} from '../lib/historyUtils';

function SnapshotDot({ hasSnapshot }) {
  return (
    <span
      className={`history-dot${hasSnapshot ? ' is-ok' : ' is-warn'}`}
      title={hasSnapshot ? '可恢复' : '无快照'}
    />
  );
}

function EmptyHistory() {
  return (
    <div className="history-empty-state history-empty-compact">
      <p>暂无执行记录。在查询页执行策略后，最近 50 次会显示在此。</p>
      <Link to="/" className="btn btn-sm btn-primary">前往查询</Link>
    </div>
  );
}

function HistoryRow({ item, onRestore, onSaveAsStrategy }) {
  const hasSnapshot = !!(item.snapshot || item.strategy_id);
  return (
    <tr
      className="history-row"
      onClick={() => onRestore(item)}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => e.key === 'Enter' && onRestore(item)}
    >
      <td className="history-col-dot"><SnapshotDot hasSnapshot={hasSnapshot} /></td>
      <td className="history-col-time">{item.time?.slice(0, 16) || '—'}</td>
      <td className="history-col-range muted">{item.start} — {item.end}</td>
      <td className="history-col-mode">{item.mode_label || '—'}</td>
      <td className="history-col-count"><strong>{item.count ?? '—'}</strong></td>
      <td className="history-col-actions" onClick={(e) => e.stopPropagation()}>
        <button type="button" className="btn btn-xs btn-primary" onClick={() => onRestore(item)}>恢复</button>
        <button type="button" className="btn btn-xs btn-ghost" onClick={() => onRestore(item, true)}>重跑</button>
        <button type="button" className="btn btn-xs btn-ghost" onClick={() => onSaveAsStrategy(item)} disabled={!hasSnapshot}>存策略</button>
      </td>
    </tr>
  );
}

function StrategySection({ group, onRestore, onSaveAsStrategy }) {
  return (
    <section className="history-strategy-section">
      <header className="history-strategy-head">
        <span className="history-strategy-dot" style={{ background: group.color }} />
        <h3>{group.name}</h3>
        <span className="history-strategy-meta">{group.count} 次 · {group.items.reduce((s, i) => s + (Number(i.count) || 0), 0).toLocaleString()} 条</span>
      </header>
      <table className="history-compact-table">
        <thead>
          <tr>
            <th aria-label="状态" />
            <th>执行时间</th>
            <th>查询时段</th>
            <th>模式</th>
            <th>结果</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {group.items.map((item, index) => (
            <HistoryRow
              key={item.ts || index}
              item={item}
              onRestore={onRestore}
              onSaveAsStrategy={onSaveAsStrategy}
            />
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState(loadHistory);
  const [filters, setFilters] = useState({ ...DEFAULT_HISTORY_FILTERS });
  const [clearOpen, setClearOpen] = useState(false);

  const refresh = useCallback(() => setItems(loadHistory()), []);

  const restore = (item, autoExecute = false) => {
    navigate('/', { state: { restore: item, autoExecute } });
  };

  const saveAsStrategy = (item) => {
    if (!item.snapshot && !item.strategy_id) {
      toast('无快照，无法存策略', 'error');
      return;
    }
    restore(item);
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('pc-open-save-strategy', {
        detail: { name: `${item.strategy}_${new Date().toISOString().slice(0, 10)}` },
      }));
    }, 400);
    toast('已恢复，请在查询页确认保存');
  };

  const strategies = useMemo(() => uniqueStrategies(items), [items]);
  const strategyCounts = useMemo(() => countByStrategy(items, filters), [items, filters]);
  const filtered = useMemo(() => applyHistoryFilters(items, filters), [items, filters]);
  const grouped = useMemo(() => {
    if (filters.strategy) return null;
    return groupHistoryByStrategy(filtered);
  }, [filtered, filters.strategy]);

  const stats = useMemo(() => ({
    total: items.length,
    filtered: filtered.length,
    rows: filtered.reduce((s, i) => s + (Number(i.count) || 0), 0),
  }), [items, filtered]);

  const resetFilters = () => setFilters({ ...DEFAULT_HISTORY_FILTERS });

  return (
    <div className="panel active history-page history-page-compact" id="panel-history">
      <SceneHubNav variant="query" />
      <header className="history-header-bar history-header-compact">
        <div className="history-header-main">
          <div className="topbar-title">查询历史</div>
          <span className="history-inline-stats muted">
            {stats.filtered}/{stats.total} 次 · {stats.rows.toLocaleString()} 条
          </span>
        </div>
        <div className="history-header-actions">
          <button type="button" className="btn btn-xs btn-ghost" onClick={() => setClearOpen(true)} disabled={!items.length}>清空</button>
        </div>
      </header>

      <div className="history-compact-bar">
        <div className="history-time-presets">
          {HISTORY_TIME_PRESETS.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`history-preset-btn${filters.timePreset === p.id ? ' is-active' : ''}`}
              onClick={() => setFilters({ ...filters, timePreset: p.id })}
            >
              {p.label}
            </button>
          ))}
        </div>
        <input
          className="history-search history-search-compact"
          placeholder="搜索…"
          value={filters.q}
          onChange={(e) => setFilters({ ...filters, q: e.target.value })}
        />
        <label className="history-check-compact">
          <input
            type="checkbox"
            checked={filters.restorableOnly}
            onChange={(e) => setFilters({ ...filters, restorableOnly: e.target.checked })}
          />
          可恢复
        </label>
        {hasActiveFilters(filters) && (
          <button type="button" className="btn btn-xs btn-ghost" onClick={resetFilters}>重置</button>
        )}
      </div>

      <div className="history-strategy-bar">
        <button
          type="button"
          className={`history-strategy-chip${!filters.strategy ? ' is-active' : ''}`}
          onClick={() => setFilters({ ...filters, strategy: '' })}
        >
          全部策略 <span>{strategyCounts[''] ?? 0}</span>
        </button>
        {strategies.map((name, index) => (
          <button
            key={name}
            type="button"
            className={`history-strategy-chip${filters.strategy === name ? ' is-active' : ''}`}
            onClick={() => setFilters({ ...filters, strategy: name })}
          >
            <span className="history-strategy-chip-dot" style={{ background: strategyColor(name, index) }} />
            {name} <span>{strategyCounts[name] || 0}</span>
          </button>
        ))}
      </div>

      <div className="history-workspace history-workspace-compact">
        {!items.length ? (
          <EmptyHistory />
        ) : !filtered.length ? (
          <div className="history-empty-state history-empty-inline">
            <p>无匹配记录</p>
            <button type="button" className="btn btn-xs btn-ghost" onClick={resetFilters}>重置</button>
          </div>
        ) : grouped ? (
          <div className="history-grouped-compact">
            {grouped.map((group) => (
              <StrategySection
                key={group.id}
                group={group}
                onRestore={restore}
                onSaveAsStrategy={saveAsStrategy}
              />
            ))}
          </div>
        ) : (
          <table className="history-compact-table history-compact-table-single">
            <thead>
              <tr>
                <th aria-label="状态" />
                <th>执行时间</th>
                <th>查询时段</th>
                <th>模式</th>
                <th>结果</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((item, index) => (
                <HistoryRow
                  key={item.ts || index}
                  item={item}
                  onRestore={restore}
                  onSaveAsStrategy={saveAsStrategy}
                />
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal open={clearOpen} title="清空历史" onClose={() => setClearOpen(false)}>
        <div className="form-modal-body">
          <p>确定清空全部 {items.length} 条历史记录？</p>
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setClearOpen(false)}>取消</button>
            <button type="button" className="btn btn-danger" onClick={() => { clearHistory(); refresh(); setClearOpen(false); toast('已清空'); }}>清空</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
