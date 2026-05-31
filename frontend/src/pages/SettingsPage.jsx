import { useSearchParams } from 'react-router-dom';
import ConfigPage from './ConfigPage';
import AdminPage from './AdminPage';
import DocsPage from './DocsPage';

const SECTIONS = [
  { id: 'system', label: '系统设置', desc: '数据库、路径与运行参数' },
  { id: 'strategy', label: '查询策略', desc: 'Pipeline 与块模板' },
  { id: 'docs', label: '使用手册', desc: '操作说明与文档' },
];

export default function SettingsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const section = searchParams.get('section') || 'system';
  const active = SECTIONS.some((s) => s.id === section) ? section : 'system';

  const setSection = (id) => {
    const next = new URLSearchParams(searchParams);
    if (id === 'system') next.delete('section');
    else next.set('section', id);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="settings-hub">
      <header className="settings-hub-header">
        <div>
          <div className="topbar-title">设置</div>
          <p className="settings-header-desc">系统配置、查询策略与使用手册</p>
        </div>
      </header>
      <nav className="settings-hub-tabs" aria-label="设置分区">
        {SECTIONS.map((s) => (
          <button
            key={s.id}
            type="button"
            className={`settings-hub-tab${active === s.id ? ' is-active' : ''}`}
            onClick={() => setSection(s.id)}
            aria-current={active === s.id ? 'page' : undefined}
          >
            <span className="settings-hub-tab-label">{s.label}</span>
            <span className="settings-hub-tab-desc">{s.desc}</span>
          </button>
        ))}
      </nav>
      <div className="settings-hub-body">
        {active === 'system' && <ConfigPage embedded />}
        {active === 'strategy' && <AdminPage embedded />}
        {active === 'docs' && <DocsPage embedded />}
      </div>
    </div>
  );
}
