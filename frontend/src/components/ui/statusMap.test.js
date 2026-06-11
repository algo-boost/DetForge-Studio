import { describe, expect, it } from 'vitest';
import { STATUS_MAP, statusLabel, statusTone } from './statusMap';

describe('statusMap', () => {
  it('maps waiting_human to warn tone', () => {
    expect(statusTone('waiting_human')).toBe('warn');
    expect(statusLabel('waiting_human')).toBe('待人工');
  });

  it('falls back for unknown status', () => {
    expect(statusLabel('custom')).toBe('custom');
    expect(statusTone('custom')).toBe('neutral');
  });

  it('includes core job statuses', () => {
    expect(STATUS_MAP.running.label).toBe('运行中');
    expect(STATUS_MAP.paused.label).toBe('已暂停');
  });
});
