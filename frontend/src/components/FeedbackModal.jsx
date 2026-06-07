import { useEffect, useMemo, useState } from 'react';
import { Modal } from './Modal';
import { ConsoleOutputContent } from './ConsolePanel';

const TYPE_LABEL = {
  error: '执行失败',
  success: '执行完成',
  info: '提示',
};

export default function FeedbackModal() {
  const [state, setState] = useState(null);

  useEffect(() => {
    const onFeedback = (e) => setState(e.detail || null);
    const onLegacyError = (e) => {
      const d = e.detail || {};
      setState({
        type: 'error',
        title: d.title || '执行失败',
        message: d.message || '',
        detail: d.detail || '',
        consoleOutput: '',
      });
    };
    window.addEventListener('pc-feedback-modal', onFeedback);
    window.addEventListener('pc-error-modal', onLegacyError);
    return () => {
      window.removeEventListener('pc-feedback-modal', onFeedback);
      window.removeEventListener('pc-error-modal', onLegacyError);
    };
  }, []);

  const type = state?.type || 'error';
  const title = state?.title || TYPE_LABEL[type] || '提示';
  const hasConsole = !!(state?.consoleOutput?.trim());
  const wide = hasConsole || !!(state?.detail?.trim());

  const consoleContent = useMemo(() => {
    if (!state) return null;
    return {
      text: state.message || '',
      type: type === 'error' ? 'error' : type === 'success' ? 'success' : 'ok',
      consoleOutput: state.consoleOutput || '',
    };
  }, [state, type]);

  if (!state) return null;

  return (
    <Modal open title={title} wide={wide} onClose={() => setState(null)}>
      <div className={`form-modal-body feedback-modal-body feedback-modal-${type}`}>
        {state.message && !hasConsole && (
          <p className="feedback-modal-message">{state.message}</p>
        )}
        {state.detail && (
          <pre className="feedback-modal-detail">{state.detail}</pre>
        )}
        {hasConsole && consoleContent && (
          <div className="feedback-modal-console">
            <ConsoleOutputContent content={consoleContent} />
          </div>
        )}
        <div className="form-actions">
          <button type="button" className="btn btn-primary" onClick={() => setState(null)}>
            知道了
          </button>
        </div>
      </div>
    </Modal>
  );
}
