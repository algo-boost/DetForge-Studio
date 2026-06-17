import { describe, expect, it } from 'vitest';
import {
  normalizePersona,
  personasForTier,
  resolveDefaultHome,
} from './personas';
import { USER_TIERS } from './nav';

describe('personas config', () => {
  it('personasForTier filters by tier', () => {
    const l1 = personasForTier(USER_TIERS.OPERATOR);
    expect(l1.map((p) => p.id)).toEqual(['delivery', 'customer_qc']);
    const l2 = personasForTier(USER_TIERS.CONFIGURER);
    expect(l2.map((p) => p.id)).toContain('sa');
    expect(l2.map((p) => p.id)).toContain('algo');
  });

  it('resolveDefaultHome returns persona landing', () => {
    expect(resolveDefaultHome('sa', USER_TIERS.CONFIGURER)).toBe('/flows/compose');
    expect(resolveDefaultHome('algo', USER_TIERS.CONFIGURER)).toBe('/query');
    expect(resolveDefaultHome('delivery', USER_TIERS.OPERATOR)).toBe('/');
  });

  it('normalizePersona falls back when tier mismatches', () => {
    expect(normalizePersona('sa', USER_TIERS.OPERATOR)).toBe('delivery');
    expect(normalizePersona('delivery', USER_TIERS.CONFIGURER)).toBe('sa');
  });
});
