import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import StatusPill from '../components/ui/StatusPill';
import { usePolling } from '../hooks/usePolling';
import { flowRunPath, RUN_STATUS_OPTIONS } from '../lib/flowsRun';

export default function FlowRunsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const statusFilter = searchParams.get('status') || '';
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const q = statusFilter ? `?status=${encodeURIComponent(statusFilter)}&limit=80` : '?limit=80';
      const r = await api.flowRunsList(q);
      if (r.success) setRuns(r.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);
  usePolling(load, { interval: 8000, immediate: false });

  const waitingCount = useMemo(
    () => runs.filter((r) => r.status === 'waiting_human').length,
    [runs],
  );

  const setStatus = (value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set('status', value);
    else next.delete('status');
    setSearchParams(next);
  };

  return (
    <div className="panel active flows-page flows-page--wide">
      <SceneHubNav variant="flows" />
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">运行记录</h1>
          <p className="flows-page-desc">
            Demo / Workflow / Kestra 执行汇总
            {waitingCount > 0 && (
              <>
                {' · '}
                <span className="flows-waiting-inline">{waitingCount} 个待人工</span>
              </>
            )}
          </p>
        </div>
        <Link to="/flows" className="btn btn-sm">Flow 目录</Link>
      </header>

      <div className="flows-status-tabs">
        {RUN_STATUS_OPTIONS.map((opt) => (
          <button
            key={opt.value || 'all'}
            type="button"
            className={`flows-status-tab${statusFilter === opt.value ? ' is-active' : ''}`}
            onClick={() => setStatus(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {loading && !runs.length ? (
        <div className="empty-state">加载中…</div>
      ) : !runs.length ? (
        <div className="empty-state">
          暂无运行记录。
          {' '}
          <Link to="/flows/demo">运行演示 Flow</Link>
        </div>
      ) : (
        <table className="flows-table flows-runs-table">
          <thead>
            <tr>
              <th>Flow</th>
              <th>来源</th>
              <th>状态</th>
              <th>创建</th>
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
                  <div className="flows-run-name">{run.name || run.flow_id || run.run_id}</div>
                  <div className="flows-run-sub">{run.flow_id || run.run_key}</div>
                </td>
                <td>{run.source}</td>
                <td>
                  <StatusPill status={run.status} />
                </td>
                <td>{run.created_at || '—'}</td>
                <td>
                  <Link to={flowRunPath(run.run_key)} className="btn btn-sm">详情</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
