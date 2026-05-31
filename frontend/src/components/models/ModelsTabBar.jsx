import { MODELS_TABS } from './modelsUtils';

const TAB_ICONS = {
  registry: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><rect x="4" y="4" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.5" /><path d="M8 8h4M8 12h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
  ),
  platform: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 14l4-8 4 5 4-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ),
  deploy: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M10 3l7 4v6l-7 4-7-4V7l7-4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" /></svg>
  ),
  train: (
    <svg viewBox="0 0 20 20" fill="none" aria-hidden="true"><path d="M4 14l4-8 4 5 4-9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
  ),
};

export default function ModelsTabBar({ activeTab, onTabChange, counts = {} }) {
  return (
    <nav className="models-tab-bar" aria-label="模型工作区">
      {MODELS_TABS.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`models-tab-bar-item${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
          aria-current={activeTab === t.id ? 'page' : undefined}
        >
          <span className="models-tab-bar-icon">{TAB_ICONS[t.id]}</span>
          <span className="models-tab-bar-text">
            <span className="models-tab-bar-label">{t.label}</span>
            <span className="models-tab-bar-desc">{t.desc}</span>
          </span>
          {counts[t.id] != null && (
            <span className="models-tab-bar-badge">{counts[t.id]}</span>
          )}
        </button>
      ))}
    </nav>
  );
}
