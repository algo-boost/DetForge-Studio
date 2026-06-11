import { describe, expect, it } from 'vitest';
import {
  filterWaitingHumanRuns,
  findGateStep,
  flowRunToGateItem,
  getGateBatchId,
  workflowRunToGateItem,
} from './useHumanGates';

describe('useHumanGates utils', () => {
  it('filterWaitingHumanRuns keeps only waiting_human', () => {
    const runs = [
      { id: 1, status: 'running' },
      { id: 2, status: 'waiting_human' },
      { id: 3, status: 'done' },
    ];
    expect(filterWaitingHumanRuns(runs)).toEqual([{ id: 2, status: 'waiting_human' }]);
  });

  it('findGateStep locates waiting step', () => {
    const detail = {
      steps: [
        { step_id: 'a', status: 'done' },
        { step_id: 'b', status: 'waiting_human' },
      ],
    };
    expect(findGateStep(detail)?.step_id).toBe('b');
  });

  it('getGateBatchId prefers child_batch_id', () => {
    expect(getGateBatchId({ child_batch_id: 'b1' })).toBe('b1');
    expect(getGateBatchId({ human_action: { batch_id: 'b2' } })).toBe('b2');
  });

  it('workflowRunToGateItem builds deep link', () => {
    const item = workflowRunToGateItem({ id: 9, template_id: 'weekly' });
    expect(item.href).toBe('/flows/runs/workflow:9');
    expect(item.kind).toBe('workflow_human_gate');
  });

  it('flowRunToGateItem maps kestra source', () => {
    const item = flowRunToGateItem({
      source: 'kestra',
      run_id: 'exec-1',
      flow_id: 'daily_ng',
      batch_id: '42',
    });
    expect(item.kind).toBe('kestra_pause');
    expect(item.subtitle).toBe('batch 42');
  });
});
