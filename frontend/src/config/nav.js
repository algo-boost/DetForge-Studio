/**
 * IISP 导航单源（U2）
 * @see docs/UI_REDESIGN_CHECKLIST.md §2
 */

export const USER_TIERS = {
  OPERATOR: 'operator',
  CONFIGURER: 'configurer',
};

/** @typedef {'operator' | 'configurer'} UserTier */

export const NAV_GROUPS = [
  {
    id: 'workbench',
    label: '工作台',
    defaultPath: '/',
    items: [
      { to: '/', label: '概览', end: true, icon: 'home', tiers: ['operator', 'configurer'] },
    ],
  },
  {
    id: 'work',
    label: '作业',
    defaultPath: '/query',
    hub: 'query',
    items: [
      { to: '/query', label: '查询', icon: 'query', tiers: ['operator', 'configurer'] },
      {
        to: '__query_results__',
        label: '查询结果',
        icon: 'query',
        matchPath: '/query-results',
        tiers: ['operator', 'configurer'],
      },
      { to: '/history', label: '查询历史', icon: 'history', tiers: ['operator', 'configurer'] },
      { to: '/strategies', label: '查询策略', icon: 'strategy', tiers: ['configurer'] },
      { to: '/manual-qc', label: '人工质检', icon: 'qc', tiers: ['operator', 'configurer'] },
      { to: '/curation', label: '筛选归档', icon: 'docs', tiers: ['operator', 'configurer'] },
      { to: '/online-predict', label: '在线预测', icon: 'predict', tiers: ['operator', 'configurer'] },
      { to: '/jobs', label: '预测任务', icon: 'jobs', tiers: ['operator', 'configurer'] },
      { to: '/models', label: '模型', icon: 'models', tiers: ['configurer'] },
    ],
  },
  {
    id: 'flows',
    label: '流水线',
    defaultPath: '/flows',
    hub: 'flows',
    items: [
      { to: '/flows', label: '编排', end: true, icon: 'strategy', tiers: ['configurer'] },
    ],
  },
  {
    id: 'platform',
    label: '平台',
    defaultPath: '/toolbox',
    hub: 'platform',
    items: [
      { to: '/toolbox', label: '工具箱', end: true, icon: 'strategy', tiers: ['configurer'] },
      { to: '/training', label: '训练平台', icon: 'sync', tiers: ['configurer'] },
      { to: '/viewer', label: '样本图库', icon: 'viewer', tiers: ['operator', 'configurer'] },
      { to: '/docs', label: '使用手册', icon: 'docs', tiers: ['operator', 'configurer'] },
      { to: '/config', label: '设置', icon: 'config', tiers: ['configurer'] },
    ],
  },
];

const WORK_PATHS = [
  '/query',
  '/query-results',
  '/history',
  '/strategies',
  '/manual-qc',
  '/curation',
  '/online-predict',
  '/jobs',
  '/models',
];

const FLOW_PATHS = ['/flows', '/workflows', '/demo'];

/**
 * @param {string} pathname
 * @returns {string}
 */
export function resolveNavGroupId(pathname) {
  const path = pathname.split('?')[0] || '/';
  if (path === '/') return 'workbench';
  if (WORK_PATHS.some((p) => path === p || path.startsWith(`${p}/`))) return 'work';
  if (FLOW_PATHS.some((p) => path === p || path.startsWith(`${p}/`))) return 'flows';
  return 'platform';
}

/**
 * @param {UserTier} tier
 * @returns {typeof NAV_GROUPS}
 */
export function navGroupsForTier(tier) {
  const t = tier === USER_TIERS.OPERATOR ? USER_TIERS.OPERATOR : USER_TIERS.CONFIGURER;
  return NAV_GROUPS.map((group) => ({
    ...group,
    items: group.items.filter((item) => (item.tiers || ['configurer']).includes(t)),
  })).filter((group) => group.items.length > 0);
}

/**
 * @param {string} groupId
 * @param {UserTier} tier
 */
export function getNavGroup(groupId, tier) {
  return navGroupsForTier(tier).find((g) => g.id === groupId) || null;
}

/** L2 专属路径前缀（L1 访问时重定向） */
const CONFIGURER_ONLY_PREFIXES = [
  '/strategies',
  '/admin',
  '/models',
  '/flows',
  '/workflows',
  '/demo',
  '/toolbox',
  '/training',
  '/config',
  '/settings',
  '/sync',
];

/**
 * @param {string} pathname
 * @param {UserTier} tier
 */
export function isPathAllowedForTier(pathname, tier) {
  if (tier !== USER_TIERS.OPERATOR) return true;
  const path = (pathname || '/').split('?')[0] || '/';
  return !CONFIGURER_ONLY_PREFIXES.some(
    (prefix) => path === prefix || path.startsWith(`${prefix}/`),
  );
}

/**
 * @param {UserTier} tier
 * @param {string} [defaultHome='/']
 */
export function fallbackPathForTier(tier, defaultHome = '/') {
  if (tier === USER_TIERS.OPERATOR) return defaultHome || '/';
  return defaultHome || '/';
}

/**
 * 扁平化当前 tier 可见的导航路径（供 Command Palette）
 * @param {UserTier} tier
 */
export function navCommandsForTier(tier) {
  const items = [];
  for (const group of navGroupsForTier(tier)) {
    for (const item of group.items) {
      if (item.to.startsWith('__')) continue;
      items.push({
        id: `nav-${item.to}`,
        label: item.label,
        group: group.label,
        path: item.to,
        keywords: [group.label, item.label],
      });
    }
  }
  return items;
}
