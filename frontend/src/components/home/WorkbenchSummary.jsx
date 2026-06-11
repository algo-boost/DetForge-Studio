import StatCard from './StatCard';

export default function WorkbenchSummary({ summary }) {
  if (!summary) return null;

  return (
    <div className="home-summary">
      <StatCard label="待办" value={summary.todo_count ?? 0} />
      <StatCard label="运行中 Flow" value={summary.running_flow_count ?? 0} />
      <StatCard label="活跃查询" value={summary.active_query_count ?? 0} />
    </div>
  );
}
