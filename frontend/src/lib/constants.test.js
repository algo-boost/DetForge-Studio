import { describe, expect, it } from 'vitest';
import {
  DEFAULT_PREDICT_SQL,
  LARGE_RESULT_THRESHOLD,
  buildPredictJobSql,
  buildSampleFunction,
} from './constants';

describe('buildPredictJobSql', () => {
  it('adds job_id filter without time range', () => {
    const sql = buildPredictJobSql('`detforge`.`predict_result`', 38);
    expect(sql).toContain('job_id = 38');
    expect(sql).not.toMatch(/BETWEEN|c_time/i);
  });

  it('returns full table select when job id missing', () => {
    expect(buildPredictJobSql('t', null)).toBe('SELECT * FROM t');
    expect(buildPredictJobSql('t', '')).toBe('SELECT * FROM t');
  });

  it('uses default table when omitted', () => {
    expect(buildPredictJobSql(undefined, 1)).toContain('predict_result');
  });
});

describe('buildSampleFunction', () => {
  it('embeds sample size and seed', () => {
    const fn = buildSampleFunction(100, 7);
    expect(fn).toContain('max_rows=100');
    expect(fn).toContain('random_seed=7');
  });
});

describe('defaults', () => {
  it('default predict sql targets predict_result', () => {
    expect(DEFAULT_PREDICT_SQL).toContain('predict_result');
  });

  it('large result threshold is 500', () => {
    expect(LARGE_RESULT_THRESHOLD).toBe(500);
  });
});
