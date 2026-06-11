import { describe, expect, it } from 'vitest';
import { isPredictResultRow, resolveItemImageSrc } from './resultImage';

describe('isPredictResultRow', () => {
  it('true when predict_result source and id present', () => {
    expect(isPredictResultRow({ predict_result_id: 9 }, 'predict_result')).toBe(true);
  });
  it('true when row has predict_result_id even on detail source', () => {
    expect(isPredictResultRow({ predict_result_id: 9 }, 'detail')).toBe(true);
  });
});

describe('resolveItemImageSrc', () => {
  it('uses preview url for predict rows', () => {
    const url = resolveItemImageSrc({ predict_result_id: 42, img_name: 'a.jpg', img_path: '/x/a.jpg' }, 'predict_result');
    expect(url).toContain('/api/forge/predict-result/42/preview');
  });
});
