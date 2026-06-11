import { NavLink, useLocation } from 'react-router-dom';
import { buildQueryResultsPath } from '../lib/queryResultsNav';

/** 同一场景内页顶快捷切换（与侧栏分组一致） */
const HUBS = {
  query: [
    { to: '/query', label: '查询', end: true },
    { to: '__results__', label: '查询结果', matchPath: '/query-results' },
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
  flows: [
    { to: '/flows', label: '编排任务', end: true, matchQuery: { tab: null } },
    { to: '/flows/assistant', label: '编排助手', matchPath: '/flows/assistant' },
    { to: '/flows?tab=history', label: '执行历史', matchQuery: { tab: 'history' } },
  ],
  platform: [
    { to: '/toolbox', label: '工具箱', end: true },
    { to: '/training', label: '训练平台' },
    { to: '/viewer', label: '样本图库' },
  ],
};

const HUB_LABELS = {
  query: '数据查询',
  qc: '质检归档',
  predict: '预测评估',
  flows: '流水线',
  platform: '平台',
};

export default function SceneHubNav({ variant, className = '' }) {
  const items = HUBS[variant];
  const location = useLocation();
  if (!items?.length) return null;

  return (
    <nav
      className={`scene-hub-nav${className ? ` ${className}` : ''}`}
      aria-label={HUB_LABELS[variant] || variant}
    >
      {items.map((item) => {
        const to = item.to === '__results__' ? buildQueryResultsPath() : item.to;
        return (
        <NavLink
          key={item.to}
          to={to}
          end={item.end}
          className={({ isActive }) => {
            let active = isActive;
            if (item.matchPath) {
              active = location.pathname === item.matchPath;
            }
            if (item.matchQuery) {
              const params = new URLSearchParams(location.search);
              const               onFlowsHub = location.pathname === '/flows'
                || location.pathname.startsWith('/flows/tasks/')
                || location.pathname === '/flows/assistant';
              active = onFlowsHub && Object.entries(item.matchQuery).every(([key, val]) => {
                const cur = params.get(key);
                if (val == null) return !cur;
                return cur === String(val);
              });
            }
            return `scene-hub-nav-item${active ? ' is-active' : ''}`;
          }}
        >
          {item.label}
        </NavLink>
        );
      })}
    </nav>
  );
}
