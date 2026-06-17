/** 全局反馈弹窗（与 FeedbackModal 事件总线对接） */

function openFeedback(detail) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('pc-feedback-modal', { detail }));
}

/** 兼容 showXxx(message, { title }) 与 showXxx({ message, title }) 两种调用方式。 */
function normalizeFeedbackArgs(arg1, arg2) {
  if (typeof arg1 === 'string') {
    const opts = arg2 && typeof arg2 === 'object' ? arg2 : {};
    return { ...opts, message: arg1 };
  }
  if (arg1 && typeof arg1 === 'object') return arg1;
  return arg2 && typeof arg2 === 'object' ? arg2 : {};
}

export function showErrorModal(arg1, arg2) {
  const {
    title = '执行失败',
    message = '',
    detail = '',
    consoleOutput = '',
  } = normalizeFeedbackArgs(arg1, arg2);
  openFeedback({ type: 'error', title, message, detail, consoleOutput });
}

export function showInfoModal(arg1, arg2) {
  const {
    title = '提示',
    message = '',
    detail = '',
  } = normalizeFeedbackArgs(arg1, arg2);
  openFeedback({ type: 'info', title, message, detail, consoleOutput: '' });
}

export function showResultModal(arg1, arg2) {
  const {
    title = '执行完成',
    message = '',
    detail = '',
    consoleOutput = '',
  } = normalizeFeedbackArgs(arg1, arg2);
  openFeedback({ type: 'success', title, message, detail, consoleOutput });
}
