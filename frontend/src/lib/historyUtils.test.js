import { describe, expect, it } from 'vitest';
import {
  applyHistoryFilters,
  executionTimeRange,
  groupHistoryByStrategy,
} from './historyUtils';

const sampleItems = [
  {
    ts: new Date().toISOString(),
    strategy: '日常捞取',
    mode_label: '规则',
    count: 120,
    snapshot: {},
  },
  {
    ts: '2026-05-29T08:00:00.000Z',
    strategy: '误检评测',
    mode_label: '代码',
    count: 50,
  },
  {
    ts: '2026-05-28T12:00:00.000Z',
    strategy: '日常捞取',
    mode_label: '对照',
    count: 200,
    strategy_id: 'preset1',
  },
];

describe('applyHistoryFilters', () => {
  it('filters by strategy', () => {
    const out = applyHistoryFilters(sampleItems, { strategy: '日常捞取' });
    expect(out).toHaveLength(2);
  });

  it('filters by time preset today includes today item', () => {
    const out = applyHistoryFilters(sampleItems, { timePreset: 'today' });
    expect(out.some((i) => i.strategy === '日常捞取' && i.count === 120)).toBe(true);
  });

  it('filters restorable only', () => {
    const out = applyHistoryFilters(sampleItems, { restorableOnly: true });
    expect(out).toHaveLength(2);
  });
});

describe('groupHistoryByStrategy', () => {
  it('groups by strategy name', () => {
    const groups = groupHistoryByStrategy(sampleItems);
    expect(groups).toHaveLength(2);
    expect(groups.find((g) => g.name === '日常捞取')?.count).toBe(2);
  });
});

describe('executionTimeRange', () => {
  it('returns null range for all', () => {
    expect(executionTimeRange('all')).toEqual({ from: null, to: null });
  });
});
