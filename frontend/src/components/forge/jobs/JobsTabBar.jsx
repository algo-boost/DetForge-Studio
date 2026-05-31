import { JOBS_TABS } from './jobUtils';

const TAB_ICONS = {
  list: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <rect x="3" y="4" width="14" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3" y="9" width="14" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
      <rect x="3" y="14" width="14" height="3" rx="1" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  ),
  create: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true">
      <circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 7v6M7 10h6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

export default function JobsTabBar({ activeTab, onTabChange, counts = {} }) {
  return (
    <nav className="pjobs-tab-bar" aria-label="预测任务工作区">
      {JOBS_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`pjobs-tab-bar-item${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
          aria-current={activeTab === t.id ? 'page' : undefined}
        >
          <span className="pjobs-tab-bar-icon">{TAB_ICONS[t.id]}</span>
          <span className="pjobs-tab-bar-text">
            <span className="pjobs-tab-bar-label">{t.label}</span>
            <span className="pjobs-tab-bar-desc">{t.desc}</span>
          </span>
          {counts[t.id] != null && counts[t.id] > 0 && (
            <span className="pjobs-tab-bar-badge">{counts[t.id]}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
