import { describe, expect, it } from 'vitest';
import { formatSampleGalleryError } from './sampleGallery';

describe('formatSampleGalleryError', () => {
  it('maps missing job', () => {
    expect(formatSampleGalleryError(new Error('作业不存在: 1'))).toContain('预测作业不存在');
  });
  it('maps viz unavailable', () => {
    expect(formatSampleGalleryError('COCOVisualizer not available')).toContain('样本图库未就绪');
  });
  it('includes context', () => {
    expect(formatSampleGalleryError('failed', '查询结果')).toContain('查询结果');
  });
});
