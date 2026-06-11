import { formatViewStats } from '../lib/consoleOutput';

export function DataFrameViewModal({ open, viewData, title, onClose }) {
  if (!open || !viewData) return null;
  const heading = title || viewData.description?.trim() || 'DataFrame 查看';
  return (
    <div className="df-modal" onClick={onClose}>
      <div className="df-modal-box df-modal-table" onClick={(e) => e.stopPropagation()}>
        <div className="df-modal-header">
          <h3 title={heading}>{heading}</h3>
          <button type="button" className="btn-icon" onClick={onClose} title="关闭">✕</button>
        </div>
        <div className="df-modal-stats">{formatViewStats(viewData)}</div>
        <div className="df-modal-body">
          <div
            className="df-table-wrap"
            dangerouslySetInnerHTML={{ __html: viewData.html || '' }}
          />
        </div>
      </div>
    </div>
  );
}
