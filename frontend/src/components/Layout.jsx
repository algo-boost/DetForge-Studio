import { Link, NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useCallback, useEffect, useState } from 'react';
import { setAppNavigate } from '../lib/appNavigate';
import { buildQueryResultsPath } from '../lib/queryResultsNav';
import { setAppTimezone } from '../lib/timezone';
import { api, toast } from '../api/client';
import { getNavGroup, resolveNavGroupId } from '../config/nav';
import { DOCUMENT_TITLE, PRODUCT_NAME, PRODUCT_NAME_ZH } from '../config/brand';
import { useUserPrefs } from '../context/UserPrefsContext';
import { useCommandPalette } from '../hooks/useCommandPalette';
import AppTopNav from './AppTopNav';
import CommandPalette from './CommandPalette';
import FeedbackModal from './FeedbackModal';
import { NavIcon } from './NavIcons';
import QueryJobsTray from './QueryJobsTray';
import ResumeJobsModal from './ResumeJobsModal';

const SIDEBAR_COLLAPSED_KEY = 'defectloop.sidebar.collapsed';

function resolveItemTo(item) {
  if (item.to === '__query_results__') return buildQueryResultsPath();
  return item.to;
}

function SidebarNavItem({ item }) {
  const location = useLocation();
  const to = resolveItemTo(item);

  if (item.matchPath) {
    const active = location.pathname === item.matchPath;
    return (
      <RouterNavLink to={to} className={`sb-item${active ? ' active' : ''}`}>
        <NavIcon name={item.icon} />
        {item.label}
      </RouterNavLink>
    );
  }

  return (
    <RouterNavLink
      to={to}
      end={item.end}
      className={({ isActive }) => `sb-item${isActive ? ' active' : ''}`}
    >
      <NavIcon name={item.icon} />
      {item.label}
    </RouterNavLink>
  );
}

export function Layout() {
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const { tier } = useUserPrefs();
  const activeGroupId = resolveNavGroupId(pathname);
  const activeGroup = getNavGroup(activeGroupId, tier);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(
    () => localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1',
  );

  const handlePaletteNavigate = useCallback((path) => {
    navigate(path);
  }, [navigate]);

  const handlePaletteEvent = useCallback(async (event) => {
    if (event === 'sync-catalog') {
      try {
        const r = await api.catalogSync();
        if (r.success) toast('Catalog 已同步', 'success');
        else toast(r.data?.error || '同步失败', 'error');
      } catch (e) {
        toast(String(e.message || e), 'error');
      }
    }
  }, []);

  const palette = useCommandPalette({
    tier,
    onNavigate: handlePaletteNavigate,
    onEvent: handlePaletteEvent,
  });

  useEffect(() => {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  useEffect(() => {
    if (pathname === '/viewer') {
      setSidebarCollapsed(true);
    }
  }, [pathname]);

  useEffect(() => {
    document.title = DOCUMENT_TITLE;
  }, []);

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
      fetch('/api/unify/status', { credentials: 'same-origin' })
        .then((r) => (r.ok ? r.json() : null))
        .then((data) => {
          if (data?.mounted) {
            fetch('/unify/', { credentials: 'same-origin' }).catch(() => {});
          }
        })
        .catch(() => {});
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
              alt={PRODUCT_NAME_ZH}
            />
            <div className="sb-brand-copy">
              <div className="sb-brand-text">{PRODUCT_NAME}</div>
              <div className="sb-brand-sub">{PRODUCT_NAME_ZH}</div>
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
        <nav className="sb-nav" aria-label={activeGroup?.label || '导航'}>
          {activeGroup && (
            <>
              <div className="sb-section-label">{activeGroup.label}</div>
              {activeGroup.items.map((item) => (
                <SidebarNavItem key={`${item.to}-${item.label}`} item={item} />
              ))}
            </>
          )}
        </nav>
      </aside>
      <div className="main-area">
        <div className="app-top-bar">
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
          <AppTopNav />
        </div>
        <CommandPalette {...palette} />
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
