import { describe, expect, it } from 'vitest';
import { flowRunPath, parseRunKeyFromParams } from './flowsRun';

describe('flowsRun', () => {
  it('flowRunPath encodes run key', () => {
    expect(flowRunPath('demo:abc-123')).toBe('/flows/runs/demo%3Aabc-123');
  });

  it('parseRunKeyFromParams maps legacy workflow run param', () => {
    const params = new URLSearchParams('run=9');
    expect(parseRunKeyFromParams(params)).toBe('workflow:9');
  });
});
