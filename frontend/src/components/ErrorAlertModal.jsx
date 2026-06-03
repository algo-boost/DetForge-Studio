import { useEffect, useState } from 'react';
import { Modal } from './Modal';

export default function ErrorAlertModal() {
  const [state, setState] = useState(null);

  useEffect(() => {
    const onShow = (e) => setState(e.detail || null);
    window.addEventListener('pc-error-modal', onShow);
    return () => window.removeEventListener('pc-error-modal', onShow);
  }, []);

  if (!state) return null;

  return (
    <Modal open title={state.title || '执行失败'} onClose={() => setState(null)}>
      <div className="form-modal-body error-alert-modal-body">
        <p className="error-alert-message">{state.message}</p>
        {state.detail ? (
          <pre className="error-alert-detail">{state.detail}</pre>
        ) : null}
        <div className="form-actions">
          <button type="button" className="btn btn-primary" onClick={() => setState(null)}>
            知道了
          </button>
        </div>
      </div>
    </Modal>
  );
}
