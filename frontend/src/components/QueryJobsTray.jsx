import { useState } from 'react';
import { Link } from 'react-router-dom';
import StatusPill from './ui/StatusPill';
import { QUERY_STATUS_MAP } from './ui/statusMap';
import { useQueryJobs } from '../context/QueryJobsContext';

const TERMINAL = new Set(['done', 'failed']);

export default function QueryJobsTray({ onOpenResult }) {
  const { jobs, runningCount } = useQueryJobs();
  const [open, setOpen] = useState(false);
  const active = jobs.filter((j) => j.status === 'pending' || j.status === 'running');
  const recent = jobs.filter((j) => TERMINAL.has(j.status)).slice(0, 8);

  if (!jobs.length && !runningCount) return null;

  return (
    <div className={`query-jobs-tray${open ? ' is-open' : ''}`}>
      <button
        type="button"
        className="query-jobs-tray-toggle"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        查询任务
        {runningCount > 0 && <span className="query-jobs-tray-badge">{runningCount}</span>}
      </button>
      {open && (
        <div className="query-jobs-tray-panel" role="dialog" aria-label="查询任务列表">
          {active.length > 0 && (
            <section>
              <header className="query-jobs-tray-section-head">进行中</header>
              <ul className="query-jobs-tray-list">
                {active.map((j) => (
                  <li key={j.id} className="query-jobs-tray-item is-active">
                    <span className="query-jobs-tray-label">{j.label || '查询'}</span>
                    <StatusPill status={j.status} map={QUERY_STATUS_MAP} size="sm" />
                  </li>
                ))}
              </ul>
            </section>
          )}
          {recent.length > 0 && (
            <section>
              <header className="query-jobs-tray-section-head">最近完成</header>
              <ul className="query-jobs-tray-list">
                {recent.map((j) => (
                  <li key={j.id} className={`query-jobs-tray-item status-${j.status}`}>
                    <span className="query-jobs-tray-label">{j.label || '查询'}</span>
                    <StatusPill status={j.status} map={QUERY_STATUS_MAP} size="sm" />
                    <span className="query-jobs-tray-meta">
                      {j.status === 'done' ? `${j.count ?? 0} 条` : (j.error || '失败')}
                    </span>
                    {j.status === 'done' && j.task_id && (
                      <button
                        type="button"
                        className="btn btn-xs btn-primary"
                        onClick={() => {
                          onOpenResult?.(j);
                          setOpen(false);
                        }}
                      >
                        查看
                      </button>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}
          <footer className="query-jobs-tray-foot">
            <Link to="/query" className="btn btn-xs btn-ghost" onClick={() => setOpen(false)}>前往查询页</Link>
          </footer>
        </div>
      )}
    </div>
  );
}
