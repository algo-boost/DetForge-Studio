import { SETTINGS_TABS } from './settingsUtils';

const TAB_ICONS = {
  connection: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><ellipse cx="10" cy="5" rx="7" ry="3" stroke="currentColor" strokeWidth="1.5" /><path d="M3 5v10c0 1.66 3.13 3 7 3s7-1.34 7-3V5" stroke="currentColor" strokeWidth="1.5" /></svg>
  ),
  project: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M8 8h4M8 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
  ),
  labels: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M5 5h10v3H5zM5 10h6v3H5zM5 15h8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
  ),
  paths: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 6h12M4 10h8M4 14h10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><rect x="3" y="4" width="14" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" /></svg>
  ),
  predict: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 3v14M3 10h14" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /><circle cx="10" cy="10" r="7" stroke="currentColor" strokeWidth="1.5" /></svg>
  ),
  viz: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="3" y="5" width="14" height="10" rx="2" stroke="currentColor" strokeWidth="1.5" /><circle cx="7" cy="9" r="1.5" fill="currentColor" /><path d="M11 12l3-3 3 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ),
  platform: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 14l4-8 4 5 4-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ),
  security: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="5" y="9" width="10" height="8" rx="1" stroke="currentColor" strokeWidth="1.5" /><path d="M7 9V6a3 3 0 016 0v3" stroke="currentColor" strokeWidth="1.5" /></svg>
  ),
  query: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="8" cy="8" r="5" stroke="currentColor" strokeWidth="1.5" /><path d="M12 12l5 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
  ),
  system: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><circle cx="10" cy="10" r="3" stroke="currentColor" strokeWidth="1.5" /><path d="M10 3v2M10 15v2M3 10h2M15 10h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
  ),
};

export default function SettingsTabBar({ activeTab, onTabChange }) {
  return (
    <nav className="settings-tab-bar" aria-label="设置工作区">
      {SETTINGS_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`settings-tab-bar-item${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
          aria-current={activeTab === t.id ? 'page' : undefined}
        >
          <span className="settings-tab-bar-icon">{TAB_ICONS[t.id]}</span>
          <span className="settings-tab-bar-text">
            <span className="settings-tab-bar-label">{t.label}</span>
            <span className="settings-tab-bar-desc">{t.desc}</span>
          </span>
        </button>
      ))}
    </nav>
  );
}

function StatusPill({ ok, labelOk, labelErr, labelPending }) {
  const cls = ok === true ? 'settings-pill settings-pill-ok' : ok === false ? 'settings-pill settings-pill-err' : 'settings-pill settings-pill-muted';
  const text = ok === true ? labelOk : ok === false ? labelErr : labelPending;
  return <span className={cls}>{text}</span>;
}

export { StatusPill };
