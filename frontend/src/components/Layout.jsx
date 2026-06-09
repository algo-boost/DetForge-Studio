import { Link, NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { setAppNavigate } from '../lib/appNavigate';
import { buildQueryResultsPath } from '../lib/queryResultsNav';
import { setAppTimezone } from '../lib/timezone';
import { api } from '../api/client';
import QueryJobsTray from './QueryJobsTray';
import FeedbackModal from './FeedbackModal';
import ResumeJobsModal from './ResumeJobsModal';

const SIDEBAR_COLLAPSED_KEY = 'defectloop.sidebar.collapsed';

const NAV_ICONS = {
  query: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="11" cy="11" r="8" /><line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  ),
  history: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />
    </svg>
  ),
  models: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
      <polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
    </svg>
  ),
  jobs: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="3" y="4" width="18" height="4" rx="1" /><rect x="3" y="10" width="18" height="4" rx="1" /><rect x="3" y="16" width="18" height="4" rx="1" />
    </svg>
  ),
  qc: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  env: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h10" />
      <circle cx="19" cy="17" r="2" />
    </svg>
  ),
  strategy: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M4 6h16M4 12h10M4 18h6" />
      <circle cx="19" cy="12" r="2" /><circle cx="19" cy="18" r="2" />
    </svg>
  ),
  config: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  docs: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  ),
  viewer: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8.5" cy="8.5" r="1.5" />
      <path d="M21 15l-5-5L5 21" />
    </svg>
  ),
  predict: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
    </svg>
  ),
  sync: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M21 12a9 9 0 0 0-9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" />
      <path d="M3 3v5h5" /><path d="M3 12a9 9 0 0 0 9 9 9.75 9.75 0 0 0 6.74-2.74L21 16" />
      <path d="M16 16h5v5" />
    </svg>
  ),
};

function NavItem({ to, end, icon, children }) {
  return (
    <RouterNavLink
      to={to}
      end={end}
      className={({ isActive }) => `sb-item${isActive ? ' active' : ''}`}
    >
      {NAV_ICONS[icon]}
      {children}
    </RouterNavLink>
  );
}

export function Layout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1',
  );

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (pathname === '/viewer') {
      setSidebarCollapsed(true);
    }
  }, [pathname]);

  useEffect(() => {
    api.getConfig().then((r) => {
      if (r.success && r.config?.timezone) setAppTimezone(r.config.timezone);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setAppNavigate(navigate);
    const warmViz = () => {
      fetch('/viz/', { credentials: 'same-origin' }).catch(() => {});
      fetch('/api/viz/status', { credentials: 'same-origin' }).catch(() => {});
      fetch('/unify/', { credentials: 'same-origin' }).catch(() => {});
      fetch('/api/unify/status', { credentials: 'same-origin' }).catch(() => {});
    };
    if (typeof requestIdleCallback === 'function') {
      requestIdleCallback(warmViz, { timeout: 4000 });
    } else {
      setTimeout(warmViz, 1500);
    }
    return () => setAppNavigate(null);
  }, [navigate]);

  return (
    <div className={`app-shell${sidebarCollapsed ? ' sidebar-collapsed' : ''}`}>
      <aside className="sidebar" aria-hidden={sidebarCollapsed}>
        <div className="sb-brand-row">
          <Link className="sb-brand" to="/">
            <img
              className="sb-brand-icon"
              src="/brand/logo-icon-32.png"
              width="32"
              height="32"
              alt="DefectLoop Studio"
            />
            <div className="sb-brand-copy">
              <div className="sb-brand-text">DefectLoop Studio</div>
              <div className="sb-brand-sub">工业缺陷检测数据闭环系统</div>
            </div>
          </Link>
          <button
            type="button"
            className="sb-toggle"
            onClick={() => setSidebarCollapsed(true)}
            aria-label="收起侧边栏"
            title="收起侧边栏"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <polyline points="15 18 9 12 15 6" />
            </svg>
          </button>
        </div>
        <nav className="sb-nav">
          <div className="sb-section-label">数据查询</div>
          <NavItem to="/" end icon="query">查询</NavItem>
          <NavItem to={buildQueryResultsPath()} icon="query">查询结果</NavItem>
          <NavItem to="/history" icon="history">查询历史</NavItem>
          <NavItem to="/strategies" icon="strategy">查询策略</NavItem>

          <div className="sb-section-label">质检归档</div>
          <NavItem to="/manual-qc" icon="qc">人工质检</NavItem>
          <NavItem to="/curation" icon="docs">筛选归档</NavItem>
          <NavItem to="/workflows" icon="strategy">工作流编排</NavItem>

          <div className="sb-section-label">预测评估</div>
          <NavItem to="/online-predict" icon="predict">在线预测</NavItem>
          <NavItem to="/jobs" icon="jobs">预测任务</NavItem>
          <NavItem to="/models" icon="models">模型</NavItem>

          <div className="sb-section-label">平台工具</div>
          <NavItem to="/demo" icon="jobs">编排演示</NavItem>
          <NavItem to="/toolbox" icon="strategy">工具箱</NavItem>
          <NavItem to="/training" icon="sync">训练平台</NavItem>
          <NavItem to="/viewer" icon="viewer">样本图库</NavItem>

          <div className="sb-nav-footer">
            <div className="sb-section-label">帮助</div>
            <NavItem to="/docs" icon="docs">使用手册</NavItem>
            <NavItem to="/config" icon="config">设置</NavItem>
          </div>
        </nav>
      </aside>
      <div className="main-area">
        {sidebarCollapsed && (
          <button
            type="button"
            className="sidebar-expand-btn"
            onClick={() => setSidebarCollapsed(false)}
            aria-label="展开侧边栏"
            title="展开侧边栏"
          >
            <img src="/brand/logo-icon-32.png" width="20" height="20" alt="" />
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
              <polyline points="9 18 15 12 9 6" />
            </svg>
          </button>
        )}
        <FeedbackModal />
        <ResumeJobsModal />
        <QueryJobsTray
          onOpenResult={(job) => {
            if (job?.task_id) {
              navigate(buildQueryResultsPath(job.task_id));
            } else {
              navigate('/query-results');
            }
          }}
        />
        <Outlet />
      </div>
    </div>
  );
}
