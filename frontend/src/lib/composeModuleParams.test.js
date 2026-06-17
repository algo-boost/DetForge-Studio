import { describe, expect, it } from 'vitest';
import {
  buildPredictComposeParams,
  buildQueryComposeParams,
  inferTimeWindowFromEnv,
  validateComposeStep,
} from './composeModuleParams';

describe('composeModuleParams', () => {
  it('inferTimeWindowFromEnv uses custom when START/END set', () => {
    const tw = inferTimeWindowFromEnv({
      START_TIME: '2026-01-01 00:00:00',
      END_TIME: '2026-01-02 00:00:00',
    });
    expect(tw.preset).toBe('custom');
    expect(tw.start_time).toContain('2026-01-01');
  });

  it('buildQueryComposeParams includes strategy_snapshot and _ui', () => {
    const params = buildQueryComposeParams({
      strategyId: 'daily_trawl',
      sql: 'SELECT 1',
      pythonCode: 'pass',
      sampleCode: '',
      filterMode: 'rules',
      flow: { version: 2, nodes: [] },
      dataSource: 'detail',
      queryEnv: { START_TIME: 'a', END_TIME: 'b' },
      predictJobId: null,
      sampleSize: 100,
      randomSeed: 42,
      uiBackendMode: 'flow',
      processPipeline: [],
      queryUiMode: 'full',
    });
    expect(params.strategy_id).toBe('daily_trawl');
    expect(params.strategy_snapshot.sql_template).toBe('SELECT 1');
    expect(params._ui.sql).toBe('SELECT 1');
    expect(params.sample_size).toBe(100);
  });

  it('buildPredictComposeParams picks first deploy model', () => {
    const params = buildPredictComposeParams({
      deploySelections: ['7', '8'],
      trainSelections: [],
      registrySelections: [],
      threshold: '0.2',
      maxSize: '1024',
      device: 'cuda:0',
      intra: 2,
      namePrefix: 'test',
      dataSourceType: 'query',
      datasetId: '',
      localDir: '',
      queryTaskId: '',
      queryIndices: null,
      projectId: 1,
      selectedDeploy: { 7: true, 8: true },
      selectedTrain: {},
      selectedRegistry: {},
      modelTab: 'deploy',
    });
    expect(params.model_id).toBe(7);
    expect(params.threshold).toBe(0.2);
    expect(params._ui.multiModelNote).toMatch(/首个所选模型/);
  });

  it('validateComposeStep requires strategy for query', () => {
    expect(validateComposeStep('query', {}, [])).toMatch(/策略/);
    expect(validateComposeStep('query', { strategy_id: 's1' }, [])).toBeNull();
  });

  it('validateComposeStep requires model for predict', () => {
    expect(validateComposeStep('predict', {}, [])).toMatch(/模型/);
    expect(validateComposeStep('predict', { model_id: 1 }, [])).toBeNull();
  });
});
