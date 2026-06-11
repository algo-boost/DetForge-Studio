import { describe, expect, it } from 'vitest';
import { parseConsoleOutput } from './consoleOutput';

describe('parseConsoleOutput', () => {
  it('returns empty arrays when output is blank', () => {
    const r = parseConsoleOutput('');
    expect(r.viewMatches).toEqual([]);
    expect(r.vizMatches).toEqual([]);
    expect(r.cleanOutput).toBe('');
  });

  it('extracts viz and view payloads', () => {
    const raw = [
      'hello',
      '__VIZ_START__',
      '{"chart":"bar","labels":["a"],"values":[1]}',
      '__VIZ_END__',
      '__VIEW_DF_START__',
      '{"description":"df1","stats":{"total_rows":1,"total_cols":2}}',
      '__VIEW_DF_END__',
      'tail',
    ].join('\n');
    const r = parseConsoleOutput(raw);
    expect(r.vizMatches).toHaveLength(1);
    expect(r.vizMatches[0].chart).toBe('bar');
    expect(r.viewMatches).toHaveLength(1);
    expect(r.cleanOutput).toContain('hello');
    expect(r.cleanOutput).toContain('tail');
    expect(r.cleanOutput).not.toContain('__VIZ_START__');
  });
});
