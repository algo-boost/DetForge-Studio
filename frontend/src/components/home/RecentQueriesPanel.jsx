import { Link } from 'react-router-dom';
import StatusPill from '../ui/StatusPill';
import { QUERY_STATUS_MAP } from '../ui/statusMap';
import { buildQueryResultsPath } from '../../lib/queryResultsNav';

export default function RecentQueriesPanel({ jobs = [] }) {
  const recent = jobs.slice(0, 8);

  if (!recent.length) {
    return (
      <div className="panel empty-state">
        暂无进行中的查询。
        {' '}
        <Link to="/query">去查询</Link>
      </div>
    );
  }

  return (
    <ul className="panel home-list">
      {recent.map((job) => (
        <li key={job.id} className="home-list-item home-list-item--compact">
          <div className="home-list-row">
            <Link
              to={job.task_id ? buildQueryResultsPath(job.task_id) : '/query-results'}
              className="home-list-link home-list-link--inline"
            >
              <div className="home-list-title">{job.label || job.id}</div>
            </Link>
            <StatusPill status={job.status} map={QUERY_STATUS_MAP} size="sm" />
          </div>
        </li>
      ))}
    </ul>
  );
}
