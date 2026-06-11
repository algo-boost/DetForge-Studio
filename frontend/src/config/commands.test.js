import { describe, expect, it } from 'vitest';
import { filterCommands, buildCommandsForTier } from './commands';
import { USER_TIERS } from './nav';

describe('commands config', () => {
  it('L1 commands exclude sync catalog', () => {
    const cmds = buildCommandsForTier(USER_TIERS.OPERATOR);
    expect(cmds.some((c) => c.id === 'action-sync-catalog')).toBe(false);
    expect(cmds.some((c) => c.id === 'nav-/query')).toBe(true);
  });

  it('L2 includes sync catalog and flows nav', () => {
    const cmds = buildCommandsForTier(USER_TIERS.CONFIGURER);
    expect(cmds.some((c) => c.id === 'action-sync-catalog')).toBe(true);
    expect(cmds.some((c) => c.id === 'nav-/flows')).toBe(true);
  });

  it('filterCommands matches label and keywords', () => {
    const cmds = buildCommandsForTier(USER_TIERS.CONFIGURER);
    const filtered = filterCommands(cmds, 'catalog');
    expect(filtered.some((c) => c.id === 'action-sync-catalog')).toBe(true);
    expect(filtered.every((c) => {
      const hay = [c.label, c.group, ...(c.keywords || [])].join(' ').toLowerCase();
      return hay.includes('catalog');
    })).toBe(true);
  });
});
