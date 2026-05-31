import { PLATFORM_TABS } from './platformUtils';

const TAB_ICONS = {
  overview: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="2" y="2" width="7" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="2" width="7" height="4" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="9" width="7" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.5"/><rect x="2" y="12" width="7" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.5"/></svg>
  ),
  discover: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="9" cy="9" r="5.5" stroke="currentColor" strokeWidth="1.5"/><path d="M13.5 13.5L17 17" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
  datasets: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><ellipse cx="10" cy="5" rx="7" ry="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="M3 5v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5V5" stroke="currentColor" strokeWidth="1.5"/><path d="M3 10v5c0 1.4 3.1 2.5 7 2.5s7-1.1 7-2.5v-5" stroke="currentColor" strokeWidth="1.5"/></svg>
  ),
  predict: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3" y="3" width="14" height="14" rx="2" stroke="currentColor" strokeWidth="1.5"/><path d="M7 10h6M10 7v6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
  jobs: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
};

export default function PlatformTabBar({ activeTab, onTabChange, counts = {} }) {
  return (
    <nav className="platform-tab-bar" aria-label="训练平台工作区">
      {PLATFORM_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`platform-tab-bar-item${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
          aria-current={activeTab === t.id ? 'page' : undefined}
        >
          <span className="platform-tab-bar-icon">{TAB_ICONS[t.id]}</span>
          <span className="platform-tab-bar-text">
            <span className="platform-tab-bar-label">{t.label}</span>
            <span className="platform-tab-bar-desc">{t.desc}</span>
          </span>
          {counts[t.id] != null && counts[t.id] > 0 && (
            <span className="platform-tab-bar-badge">{counts[t.id]}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
