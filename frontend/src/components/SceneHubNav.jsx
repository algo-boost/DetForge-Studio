import { NavLink } from 'react-router-dom';

/** 同一场景内页顶快捷切换（与侧栏分组一致，不含使用手册等全局页） */
const HUBS = {
  query: [
    { to: '/', label: '查询', end: true },
    { to: '/history', label: '查询历史' },
    { to: '/strategies', label: '查询策略' },
  ],
  qc: [
    { to: '/manual-qc', label: '人工质检' },
    { to: '/curation', label: '筛选归档' },
  ],
  predict: [
    { to: '/online-predict', label: '在线预测' },
    { to: '/jobs', label: '预测任务' },
    { to: '/models', label: '模型' },
  ],
};

const HUB_LABELS = {
  query: '数据查询',
  qc: '质检归档',
  predict: '预测评估',
};

export default function SceneHubNav({ variant, className = '' }) {
  const items = HUBS[variant];
  if (!items?.length) return null;

  return (
    <nav
      className={`scene-hub-nav${className ? ` ${className}` : ''}`}
      aria-label={HUB_LABELS[variant] || variant}
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
