import { NavLink } from 'react-router-dom';

const HUBS = {
  query: [
    { to: '/', label: '查询', end: true },
    { to: '/history', label: '查询历史' },
    { to: '/manual-qc', label: '人工质检' },
    { to: '/curation', label: '筛选归档' },
  ],
  predict: [
    { to: '/online-predict', label: '在线预测' },
    { to: '/jobs', label: '预测任务' },
    { to: '/models', label: '模型' },
  ],
};

export default function SceneHubNav({ variant, className = '' }) {
  const items = HUBS[variant];
  if (!items?.length) return null;

  const label = variant === 'query' ? '数据查询' : '预测评估';

  return (
    <nav
      className={`scene-hub-nav${className ? ` ${className}` : ''}`}
      aria-label={label}
    >
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) => `scene-hub-nav-item${isActive ? ' is-active' : ''}`}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}
