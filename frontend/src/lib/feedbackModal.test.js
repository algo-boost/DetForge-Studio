import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { showErrorModal, showInfoModal, showResultModal } from './feedbackModal';

describe('feedbackModal', () => {
  beforeEach(() => {
    vi.stubGlobal('window', { dispatchEvent: vi.fn() });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('showInfoModal accepts (message, { title }) legacy form', () => {
    showInfoModal('已提交后台', { title: '已提交' });
    const detail = window.dispatchEvent.mock.calls[0][0].detail;
    expect(detail.type).toBe('info');
    expect(detail.title).toBe('已提交');
    expect(detail.message).toBe('已提交后台');
  });

  it('showErrorModal accepts object form', () => {
    showErrorModal({ title: '失败', message: '网络错误' });
    const detail = window.dispatchEvent.mock.calls[0][0].detail;
    expect(detail.message).toBe('网络错误');
  });

  it('showResultModal accepts (message, options) with detail', () => {
    showResultModal('完成', { title: 'OK', detail: 'path/to/x' });
    const detail = window.dispatchEvent.mock.calls[0][0].detail;
    expect(detail.type).toBe('success');
    expect(detail.detail).toBe('path/to/x');
  });
});
