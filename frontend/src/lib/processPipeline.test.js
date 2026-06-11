import { describe, expect, it } from 'vitest';
import {
  defaultPipelineFromPresets,
  ensureProcessPipeline,
  moveStep,
  normalizeProcessPipeline,
} from './processPipeline';

describe('processPipeline', () => {
  it('ensureProcessPipeline returns an array', () => {
    const pipe = ensureProcessPipeline({
      python_presets: ['observe', 'filter'],
    });
    expect(Array.isArray(pipe)).toBe(true);
    expect(pipe.length).toBeGreaterThan(0);
    expect(pipe[0].template_id).toBeTruthy();
  });

  it('normalizes legacy { steps } object', () => {
    const pipe = normalizeProcessPipeline({
      version: 1,
      steps: [{ template_id: 'preset_observe', params: {} }],
    });
    expect(Array.isArray(pipe)).toBe(true);
    expect(pipe[0].template_id).toBe('preset_observe');
  });

  it('defaultPipelineFromPresets builds observe+filter chain', () => {
    const pipe = defaultPipelineFromPresets(['observe', 'filter']);
    expect(pipe.map((s) => s.template_id)).toContain('preset_apply_filter_rules');
  });

  it('moveStep swaps adjacent items', () => {
    const a = { id: 'a', template_id: 'x', params: {} };
    const b = { id: 'b', template_id: 'y', params: {} };
    const next = moveStep([a, b], 0, 1);
    expect(next[0].id).toBe('b');
    expect(next[1].id).toBe('a');
  });
});
