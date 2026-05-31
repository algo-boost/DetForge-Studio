import { describe, expect, it } from 'vitest';
import { buildArchiveEntries, toSqlTime } from './format';

describe('toSqlTime', () => {
  it('pads seconds for datetime-local value', () => {
    expect(toSqlTime('2026-05-30T18:30')).toBe('2026-05-30 18:30:00');
  });
  it('returns empty for falsy', () => {
    expect(toSqlTime('')).toBe('');
  });
  it('keeps value that already has seconds', () => {
    expect(toSqlTime('2026-05-30T18:30:45')).toBe('2026-05-30 18:30:45');
  });
});

describe('buildArchiveEntries', () => {
  it('drops rows without SN and trims fields', () => {
    const out = buildArchiveEntries([
      { sn: ' SN1 ', path: '/a.png', defect_type: ' 划伤 ', qc_category: '拍不到', note: '' },
      { sn: '', path: '/b.png' },
    ]);
    expect(out).toHaveLength(1);
    expect(out[0]).toEqual({ product_no: 'SN1', customer_img_path: '/a.png', defect_type: '划伤', qc_category: '拍不到', note: undefined });
  });
});
