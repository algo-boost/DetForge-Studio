import { MQC_TABS } from './manualQcUtils';

const TAB_ICONS = {
  archive: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 6h12M4 10h8M4 14h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/><rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5"/></svg>
  ),
  batch: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="3" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/><rect x="3" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/><rect x="11" y="11" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.5"/></svg>
  ),
  query: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 4h12v12H4z" stroke="currentColor" strokeWidth="1.5"/><path d="M7 8h6M7 11h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
  records: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5"/><path d="M10 6v4l3 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
  settings: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="2.5" stroke="currentColor" strokeWidth="1.5"/><path d="M10 3v2M10 15v2M3 10h2M15 10h2M5.05 5.05l1.41 1.41M13.54 13.54l1.41 1.41M5.05 14.95l1.41-1.41M13.54 6.46l1.41-1.41" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/></svg>
  ),
  library: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 4h5v12H4zM11 4h5v8h-5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/><path d="M11 14h5v2h-5z" stroke="currentColor" strokeWidth="1.5"/></svg>
  ),
};

export default function ManualQcTabBar({ activeTab, onTabChange, counts = {} }) {
  return (
    <nav className="mqc-tab-bar" aria-label="人工质检工作区">
      {MQC_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`mqc-tab-bar-item${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
          data-testid={`mqc-tab-${t.id}`}
          aria-current={activeTab === t.id ? 'page' : undefined}
        >
          <span className="mqc-tab-bar-icon">{TAB_ICONS[t.id]}</span>
          <span className="mqc-tab-bar-text">
            <span className="mqc-tab-bar-label">{t.label}</span>
            <span className="mqc-tab-bar-desc">{t.desc}</span>
          </span>
          {counts[t.id] != null && counts[t.id] > 0 && (
            <span className="mqc-tab-bar-badge">{counts[t.id]}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
