import { describe, expect, it } from 'vitest';
import { runTimeWindowToEnv } from './timeWindow';

describe('timeWindow', () => {
  it('runTimeWindowToEnv maps yesterday preset', () => {
    const env = runTimeWindowToEnv({ preset: 'yesterday' });
    expect(env.START_TIME).toMatch(/\d{4}-\d{2}-\d{2}/);
    expect(env.END_TIME).toMatch(/\d{4}-\d{2}-\d{2}/);
  });
});
