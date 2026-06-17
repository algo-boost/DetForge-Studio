import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, toast } from '../../api/client';
import HumanGatesPanel from './HumanGatesPanel';
import StatusPill from '../ui/StatusPill';
import { useHumanGates } from '../../hooks/useHumanGates';
import { usePolling } from '../../hooks/usePolling';
import { flowRunPath, flowTaskPath, RUN_STATUS_OPTIONS } from '../../lib/flowsRun';

/**
 * 执行历史 + 待人工卡点（Flows 目录 / 首页跳转共用）。
 */
export default function FlowRunsHistoryPanel({ onResume, showGates = true }) {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get('status') || '';
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);
  const { items: gateItems, count: gateCount, reload: reloadGates } = useHumanGates();

  const loadRuns = useCallback(async () => {
    setLoading(true);
    try {
      const q = statusFilter
        ? `?status=${encodeURIComponent(statusFilter)}&limit=80`
        : '?limit=80';
      const r = await api.flowRunsList(q);
      if (r.success) setRuns(r.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { loadRuns(); }, [loadRuns]);
  usePolling(loadRuns, { interval: 8000, immediate: false });

  const waitingInList = useMemo(
    () => runs.filter((r) => r.status === 'waiting_human').length,
    [runs],
  );

  const setStatus = (value) => {
    const next = new URLSearchParams(searchParams);
    next.set('tab', 'history');
    if (value) next.set('status', value);
    else next.delete('status');
    setSearchParams(next);
  };

  const handleResume = async (item) => {
    if (onResume) {
      await onResume(item);
      await reloadGates();
      await loadRuns();
    }
  };

  return (
    <>
      {showGates && gateCount > 0 && (
        <section className="flows-gates-section">
          <div className="flows-section-head">
            <h2 className="flows-section-title">
              待人工处理
              <span className="flows-gate-badge">{gateCount}</span>
            </h2>
            {statusFilter !== 'waiting_human' && (
              <button
                type="button"
                className="btn btn-sm btn-ghost"
                onClick={() => setStatus('waiting_human')}
              >
                筛选待人工
              </button>
            )}
          </div>
          <HumanGatesPanel items={gateItems} onResume={handleResume} compact />
        </section>
      )}

      <div className="flows-status-tabs flows-runs-filter-tabs">
        {RUN_STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value || 'all'}
            type="button"
            className={`flows-status-tab${statusFilter === opt.value ? ' is-active' : ''}`}
            onClick={() => setStatus(opt.value)}
          >
            {opt.label}
            {opt.value === 'waiting_human' && gateCount > 0 && (
              <span className="flows-tab-badge">{gateCount}</span>
            )}
          </button>
        ))}
      </div>

      {statusFilter === 'waiting_human' && !loading && waitingInList === 0 && gateCount > 0 && (
        <p className="flows-history-hint muted">
          列表可能尚未刷新；请使用上方「待人工处理」继续，或稍候自动刷新。
        </p>
      )}

      {loading && !runs.length ? (
        <div className="empty-state">加载中…</div>
      ) : !runs.length ? (
        <div className="empty-state">
          {statusFilter ? '该状态下暂无运行记录。' : '暂无执行记录。'}
          {' '}
          <Link to="/flows/compose">去组合编排运行</Link>
        </div>
      ) : (
        <table className="flows-table flows-runs-table">
          <thead>
            <tr>
              <th>流水线</th>
              <th>运行 ID</th>
              <th>来源</th>
              <th>状态</th>
              <th>时间</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {runs.map((run) => (
              <tr
                key={run.run_key}
                className={run.status === 'waiting_human' ? 'flows-row-waiting' : ''}
              >
                <td>
                  {run.flow_id ? (
                    <Link to={flowTaskPath(run.flow_id, run.source)} className="flows-run-name">
                      {run.name || run.flow_id}
                    </Link>
                  ) : (
                    <div className="flows-run-name">{run.name || '—'}</div>
                  )}
                  {run.flow_id && <div className="flows-run-sub">{run.flow_id}</div>}
                </td>
                <td className="flows-table-mono">{run.run_id}</td>
                <td>{run.source === 'workflow' ? '组合编排' : run.source}</td>
                <td><StatusPill status={run.status} /></td>
                <td>{run.created_at || '—'}</td>
                <td>
                  <Link to={flowRunPath(run.run_key)} className="btn btn-sm">详情</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
