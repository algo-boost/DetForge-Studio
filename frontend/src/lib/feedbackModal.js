/** 全局反馈弹窗（与 FeedbackModal 事件总线对接） */

function openFeedback(detail) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('pc-feedback-modal', { detail }));
}

export function showErrorModal({
  title = '执行失败',
  message = '',
  detail = '',
  consoleOutput = '',
} = {}) {
  openFeedback({ type: 'error', title, message, detail, consoleOutput });
}

export function showInfoModal({
  title = '提示',
  message = '',
  detail = '',
} = {}) {
  openFeedback({ type: 'info', title, message, detail, consoleOutput: '' });
}

export function showResultModal({
  title = '执行完成',
  message = '',
  detail = '',
  consoleOutput = '',
} = {}) {
  openFeedback({ type: 'success', title, message, detail, consoleOutput });
}
