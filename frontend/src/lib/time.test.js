import { describe, expect, it } from 'vitest';
import { setTimePreset, toLocalInput } from './time';

describe('toLocalInput', () => {
  it('formats datetime-local string', () => {
    const d = new Date(2026, 4, 30, 9, 5);
    expect(toLocalInput(d)).toBe('2026-05-30T09:05');
  });
});

describe('setTimePreset', () => {
  it('returns start/end for today', () => {
    const { start, end } = setTimePreset('today');
    expect(start).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(end).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/);
    expect(start <= end).toBe(true);
  });

  it('returns yesterday range ending at 23:59', () => {
    const { end } = setTimePreset('yesterday');
    expect(end.endsWith('T23:59')).toBe(true);
  });

  it('defaults to 30days for unknown preset', () => {
    const { start, end } = setTimePreset('unknown');
    expect(start).toBeTruthy();
    expect(end).toBeTruthy();
  });
});
