import { describe, expect, it } from 'vitest';
import { navGroupsForTier, resolveNavGroupId, USER_TIERS, isPathAllowedForTier } from './nav';

describe('nav config', () => {
  it('resolveNavGroupId maps paths to groups', () => {
    expect(resolveNavGroupId('/')).toBe('workbench');
    expect(resolveNavGroupId('/query')).toBe('work');
    expect(resolveNavGroupId('/query-results')).toBe('work');
    expect(resolveNavGroupId('/flows')).toBe('flows');
    expect(resolveNavGroupId('/flows/runs')).toBe('flows');
    expect(resolveNavGroupId('/flows/kestra')).toBe('flows');
    expect(resolveNavGroupId('/toolbox')).toBe('platform');
    expect(resolveNavGroupId('/config')).toBe('platform');
  });

  it('L1 operator hides configurer-only items', () => {
    const groups = navGroupsForTier(USER_TIERS.OPERATOR);
    const work = groups.find((g) => g.id === 'work');
    const labels = work.items.map((i) => i.label);
    expect(labels).toContain('查询');
    expect(labels).not.toContain('查询策略');
    expect(labels).not.toContain('模型');
    expect(groups.find((g) => g.id === 'flows')).toBeUndefined();
  });

  it('L2 configurer includes flows and strategies', () => {
    const groups = navGroupsForTier(USER_TIERS.CONFIGURER);
    expect(groups.find((g) => g.id === 'flows')).toBeTruthy();
    const work = groups.find((g) => g.id === 'work');
    expect(work.items.some((i) => i.label === '查询策略')).toBe(true);
  });

  it('isPathAllowedForTier blocks L1 from configurer routes', () => {
    expect(isPathAllowedForTier('/query', USER_TIERS.OPERATOR)).toBe(true);
    expect(isPathAllowedForTier('/flows', USER_TIERS.OPERATOR)).toBe(false);
    expect(isPathAllowedForTier('/toolbox', USER_TIERS.OPERATOR)).toBe(false);
    expect(isPathAllowedForTier('/strategies', USER_TIERS.OPERATOR)).toBe(false);
    expect(isPathAllowedForTier('/flows', USER_TIERS.CONFIGURER)).toBe(true);
  });
});
