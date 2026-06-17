/**
 * Command Palette 静态命令（U5）
 */

import { navCommandsForTier, USER_TIERS } from './nav';

/** @typedef {{ id: string; label: string; group: string; keywords?: string[]; tiers?: string[]; action: { type: 'navigate'; path: string } | { type: 'event'; event: string } }} PaletteCommand */

/** @type {PaletteCommand[]} */
export const STATIC_ACTION_COMMANDS = [
  {
    id: 'action-sync-catalog',
    label: '同步 Catalog',
    group: '操作',
    keywords: ['catalog', 'sync', '同步', '工具箱'],
    tiers: [USER_TIERS.CONFIGURER],
    action: { type: 'event', event: 'sync-catalog' },
  },
  {
    id: 'action-demo-flow',
    label: '打开编排演示',
    group: '操作',
    keywords: ['demo', 'flow', '演示'],
    tiers: [USER_TIERS.CONFIGURER],
    action: { type: 'navigate', path: '/flows/demo' },
  },
  {
    id: 'action-compose-flow',
    label: '打开组合编排',
    group: '操作',
    keywords: ['compose', '编排', 'flow', '流水线'],
    tiers: [USER_TIERS.CONFIGURER],
    action: { type: 'navigate', path: '/flows/compose' },
  },
  {
    id: 'action-new-query',
    label: '新建查询',
    group: '操作',
    keywords: ['query', 'sql', '查询'],
    tiers: [USER_TIERS.OPERATOR, USER_TIERS.CONFIGURER],
    action: { type: 'navigate', path: '/query' },
  },
];

/**
 * @param {import('./nav').UserTier} tier
 * @returns {PaletteCommand[]}
 */
export function buildCommandsForTier(tier) {
  const navItems = navCommandsForTier(tier).map((item) => ({
    id: item.id,
    label: item.label,
    group: item.group,
    keywords: item.keywords,
    tiers: [USER_TIERS.OPERATOR, USER_TIERS.CONFIGURER],
    action: { type: 'navigate', path: item.path },
  }));

  const actions = STATIC_ACTION_COMMANDS.filter(
    (cmd) => !cmd.tiers || cmd.tiers.includes(tier),
  );

  return [...navItems, ...actions];
}

/**
 * @param {PaletteCommand[]} commands
 * @param {string} query
 */
export function filterCommands(commands, query) {
  const q = (query || '').trim().toLowerCase();
  if (!q) return commands;
  return commands.filter((cmd) => {
    const hay = [cmd.label, cmd.group, ...(cmd.keywords || [])].join(' ').toLowerCase();
    return hay.includes(q);
  });
}
