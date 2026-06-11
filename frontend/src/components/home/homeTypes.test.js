import { describe, expect, it } from 'vitest';
import { TODO_STATUS_LABEL } from './homeTypes';

describe('homeTypes', () => {
  it('maps todo status labels', () => {
    expect(TODO_STATUS_LABEL.waiting_human).toBe('待人工');
    expect(TODO_STATUS_LABEL.pending).toBe('待处理');
  });
});
