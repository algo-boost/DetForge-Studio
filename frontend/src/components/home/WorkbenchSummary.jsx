import { Link } from 'react-router-dom';
import StatCard from './StatCard';

export default function WorkbenchSummary({ summary }) {
  if (!summary) return null;

  const waiting = summary.waiting_human_count ?? 0;
  const running = summary.running_flow_count ?? 0;

  return (
    <div className="home-summary">
      <StatCard label="待办" value={summary.todo_count ?? 0} />
      <Link to="/flows?tab=history&status=waiting_human" className="home-summary-link">
        <StatCard label="待人工" value={waiting} />
      </Link>
      <Link to="/flows?tab=history&status=running" className="home-summary-link">
        <StatCard label="运行中" value={running} />
      </Link>
      <StatCard label="活跃查询" value={summary.active_query_count ?? 0} />
    </div>
  );
}
