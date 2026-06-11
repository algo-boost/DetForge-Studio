import { Link } from 'react-router-dom';
import { useQueryJobs } from '../context/QueryJobsContext';
import { useWorkbenchData } from '../hooks/useWorkbenchData';
import ActiveFlowsPanel from '../components/home/ActiveFlowsPanel';
import HomeSection from '../components/home/HomeSection';
import QuickActions from '../components/home/QuickActions';
import RecentQueriesPanel from '../components/home/RecentQueriesPanel';
import TodoList from '../components/home/TodoList';
import WorkbenchSummary from '../components/home/WorkbenchSummary';

export default function HomePage() {
  const { jobs } = useQueryJobs();
  const {
    todos,
    summary,
    flows,
    busy,
    syncCatalog,
    resumeKestra,
  } = useWorkbenchData();

  return (
    <div className="panel active home-page">
      <header className="page-header">
        <h1>工作台</h1>
        <p>待办、进行中的 Flow 与最近查询</p>
      </header>

      <QuickActions busy={busy} onSyncCatalog={syncCatalog} />
      <WorkbenchSummary summary={summary} />

      <div className="panel-grid-3">
        <HomeSection title="待办">
          <TodoList items={todos} onResumeKestra={resumeKestra} />
        </HomeSection>
        <HomeSection title="Flow 卡点">
          <ActiveFlowsPanel flows={flows} />
        </HomeSection>
        <HomeSection title="最近查询">
          <RecentQueriesPanel jobs={jobs} />
        </HomeSection>
      </div>

      <p className="home-footer-hint muted">
        按 <kbd>⌘K</kbd> 打开命令面板，快速跳转页面。
        <Link to="/config"> 设置</Link>
        中可调整视图与默认首页。
      </p>
    </div>
  );
}
