import { describe, expect, it } from 'vitest';
import {
  formatPredictJobLabel,
  parsePredictJobIdFromSql,
  predictJobModelName,
  resolvePredictJobId,
} from './predictJob';

describe('parsePredictJobIdFromSql', () => {
  it('parses job_id from WHERE clause', () => {
    expect(parsePredictJobIdFromSql('SELECT * FROM t WHERE job_id = 38')).toBe(38);
  });
  it('returns null when missing', () => {
    expect(parsePredictJobIdFromSql('SELECT 1')).toBeNull();
  });
});

describe('predictJobModelName', () => {
  it('reads params.model_name first', () => {
    expect(predictJobModelName({ name: 'batch', params: { model_name: 'V28_19plus' } })).toBe('V28_19plus');
  });
  it('parses suffix after middle dot from name', () => {
    expect(predictJobModelName({ name: '人为制造缺陷 · V17_28plus', params: {} })).toBe('V17_28plus');
  });
});

describe('formatPredictJobLabel', () => {
  it('includes id model and progress', () => {
    expect(formatPredictJobLabel({
      id: 38,
      name: 'test · MyModel',
      done: 100,
      total: 100,
      params: {},
    })).toBe('#38 · MyModel · 100/100 张');
  });
});

describe('resolvePredictJobId', () => {
  it('prefers URL param', async () => {
    const id = await resolvePredictJobId({ urlJobId: '42', recentJobs: [{ id: 1 }] });
    expect(id).toBe(42);
  });
  it('falls back to most recent job', async () => {
    const id = await resolvePredictJobId({ recentJobs: [{ id: 9 }, { id: 8 }] });
    expect(id).toBe(9);
  });
  it('falls back to SQL parse', async () => {
    const id = await resolvePredictJobId({
      sql: 'SELECT * FROM predict_result WHERE job_id = 7',
      recentJobs: [],
    });
    expect(id).toBe(7);
  });
});
