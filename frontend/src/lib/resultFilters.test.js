import { describe, expect, it } from 'vitest';
import {
  DEFAULT_RESULT_FILTER,
  buildFilterHint,
  collectFilterOptions,
  getProductNo,
  getProductType,
  isFilterActive,
  itemMatchesFilter,
} from './resultFilters';

const sample = {
  c_time: '2026-05-30 12:00:00',
  product_type: 'DoorPanel',
  product_no: 'SN123',
  product_id: 'PID1',
  position: 'front',
  check_status: '1',
  img_name: 'img_a.jpg',
  annotations: [{ category: 'scratch', score: 0.85 }],
};

describe('itemMatchesFilter', () => {
  it('matches empty filter', () => {
    expect(itemMatchesFilter(sample, DEFAULT_RESULT_FILTER)).toBe(true);
  });

  it('filters by product type substring', () => {
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, productType: 'Door' })).toBe(true);
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, productType: 'xxx' })).toBe(false);
  });

  it('filters NG/OK status', () => {
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, status: '1' })).toBe(true);
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, status: '0' })).toBe(false);
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, status: 'ng' })).toBe(true);
  });

  it('filters by min score', () => {
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, minScore: '0.8' })).toBe(true);
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, minScore: '0.9' })).toBe(false);
  });

  it('filters by category in annotations', () => {
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, category: 'scratch' })).toBe(true);
    expect(itemMatchesFilter(sample, { ...DEFAULT_RESULT_FILTER, category: 'dent' })).toBe(false);
  });
});

describe('getProductNo / getProductType', () => {
  it('reads SN alias', () => {
    expect(getProductNo({ SN: 'X1' })).toBe('X1');
  });

  it('reads result_product_type fallback', () => {
    expect(getProductType({ result_product_type: 'T1' })).toBe('T1');
  });
});

describe('collectFilterOptions', () => {
  it('aggregates distinct values', () => {
    const opts = collectFilterOptions([sample, { ...sample, product_no: 'SN456', position: 'back' }]);
    expect(opts.productTypes).toContain('DoorPanel');
    expect(opts.productNos).toContain('SN123');
    expect(opts.positions).toContain('back');
  });
});

describe('buildFilterHint / isFilterActive', () => {
  it('builds human readable hint', () => {
    const hint = buildFilterHint({ ...DEFAULT_RESULT_FILTER, status: '1', productNo: 'SN' });
    expect(hint.join(' · ')).toMatch(/NG/);
    expect(hint.join(' · ')).toMatch(/SN/);
  });

  it('detects active filters', () => {
    expect(isFilterActive(DEFAULT_RESULT_FILTER)).toBe(false);
    expect(isFilterActive({ ...DEFAULT_RESULT_FILTER, name: 'a' })).toBe(true);
  });
});
