import { formatViewStats } from '../lib/consoleOutput';

export function DataFrameViewModal({ open, viewData, title, onClose }) {
  if (!open || !viewData) return null;
  const heading = title || viewData.description?.trim() || 'DataFrame 查看';
  return (
    <div className="df-modal" onClick={onClose}>
      <div className="df-modal-box" onClick={(e) => e.stopPropagation()}>
        <div className="df-modal-header">
          <h3>{heading}</h3>
          <button type="button" className="btn-icon" onClick={onClose} title="关闭">✕</button>
        </div>
        <div className="df-modal-stats">{formatViewStats(viewData)}</div>
        <div
          className="df-modal-body"
          dangerouslySetInnerHTML={{ __html: viewData.html || '' }}
        />
      </div>
    </div>
  );
}
