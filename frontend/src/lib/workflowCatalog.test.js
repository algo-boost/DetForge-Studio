import { describe, expect, it } from 'vitest';
import {
  buildComposeDefinition,
  buildLinearComposeDefinition,
  COMPOSE_MODULES,
  composeStepHints,
  defaultComposeStepParams,
  defaultComposePipelineState,
  encodeStepId,
  MVP_COMPOSE_STEP_IDS,
  normalizeFlowId,
  reindexComposeSteps,
} from './composeModules';

describe('composeModules', () => {
  it('registers all workflow step kinds', () => {
    expect(Object.keys(COMPOSE_MODULES)).toContain('query');
    expect(Object.keys(COMPOSE_MODULES)).toContain('predict');
    expect(Object.keys(COMPOSE_MODULES)).toContain('query_predict');
    expect(MVP_COMPOSE_STEP_IDS).toEqual(['query', 'predict']);
  });

  it('normalizes flow id', () => {
    expect(normalizeFlowId('Daily_FP')).toBe('flow_daily_fp');
  });

  it('encodes step ids', () => {
    expect(encodeStepId('flow_test', 2)).toBe('flow_test.s02');
  });

  it('buildComposeDefinition binds predict task_id with stable step id', () => {
    const d = buildComposeDefinition([
      { moduleId: 'query', params: { strategy_id: 'daily_trawl' } },
      { moduleId: 'predict', params: { model_id: 2 } },
    ], { flowId: 'flow_demo' });
    expect(d.steps).toHaveLength(2);
    expect(d.steps[0].id).toBe('flow_demo.s01');
    expect(d.steps[1].params.task_id).toBe('{{steps.flow_demo.s01.task_id}}');
    expect(d.steps[0].params.time_window).toBe('{{params.time_window}}');
  });

  it('query_predict chain binds job_id from predict step', () => {
    const d = buildComposeDefinition([
      { moduleId: 'query', params: { strategy_id: 's1' } },
      { moduleId: 'predict', params: { model_id: 1 } },
      { moduleId: 'query_predict', params: { strategy_id: 's2' } },
    ], { flowId: 'flow_chain' });
    expect(d.steps[2].params.predict_job_id).toBe('{{steps.flow_chain.s02.job_id}}');
  });

  it('buildLinearComposeDefinition keeps legacy module keys', () => {
    const d = buildLinearComposeDefinition({
      query: { strategy_id: 's1' },
      predict: { model_id: 1 },
    }, 'flow_legacy');
    expect(d.steps[1].params.task_id).toBe('{{steps.flow_legacy.s01.task_id}}');
  });

  it('composeStepHints warns when upstream missing', () => {
    const hints = composeStepHints([{ uid: 'flow_x.s01', moduleId: 'predict', params: {} }], 0);
    expect(hints[0].ok).toBe(false);
  });

  it('defaultComposePipelineState uses encoded uids', () => {
    const steps = defaultComposePipelineState('flow_draft');
    expect(steps[0].uid).toBe('flow_draft.s01');
  });

  it('reindexComposeSteps updates order', () => {
    const rows = reindexComposeSteps('flow_a', [
      { moduleId: 'predict', params: {} },
      { moduleId: 'query', params: {} },
    ]);
    expect(rows[0].uid).toBe('flow_a.s01');
    expect(rows[1].uid).toBe('flow_a.s02');
  });

  it('defaultComposeStepParams includes schema defaults', () => {
    expect(defaultComposeStepParams('predict').threshold).toBe(0.1);
  });
});
