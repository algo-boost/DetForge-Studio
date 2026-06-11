import { useCallback, useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { navGroupsForTier, resolveNavGroupId } from '../config/nav';
import { useUserPrefs } from '../context/UserPrefsContext';
import { usePolling } from '../hooks/usePolling';
import ModeSwitch from './ModeSwitch';

export default function AppTopNav() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { tier } = useUserPrefs();
  const groups = navGroupsForTier(tier);
  const activeId = resolveNavGroupId(pathname);
  const [todoCount, setTodoCount] = useState(0);

  const loadTodoCount = useCallback(() => {
    api.workbenchSummary()
      .then((r) => {
        if (r.success) setTodoCount(Number(r.data?.todo_count) || 0);
      })
      .catch(() => {});
  }, []);

  useEffect(() => { loadTodoCount(); }, [loadTodoCount, pathname]);
  usePolling(loadTodoCount, { interval: 15000, immediate: false });

  return (
    <header className="app-top-nav" aria-label="主导航">
      <ModeSwitch />
      <nav className="app-top-nav-tabs">
        {groups.map((group) => {
          const isActive = group.id === activeId;
          const showBadge = group.id === 'workbench' && todoCount > 0;
          return (
            <button
              key={group.id}
              type="button"
              className={`app-top-nav-tab${isActive ? ' is-active' : ''}`}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => {
                if (!isActive) navigate(group.defaultPath);
              }}
            >
              <span>{group.label}</span>
              {showBadge && (
                <span className="app-top-nav-badge" aria-label={`${todoCount} 项待办`}>
                  {todoCount > 99 ? '99+' : todoCount}
                </span>
              )}
            </button>
          );
        })}
      </nav>
      <div className="app-top-nav-hint" aria-hidden>
        <kbd>⌘K</kbd> 命令
      </div>
    </header>
  );
}
