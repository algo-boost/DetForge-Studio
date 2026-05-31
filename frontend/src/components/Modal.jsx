export function Modal({ open, title, onClose, children, wide }) {
  if (!open) return null;
  return (
    <div className="df-modal" onClick={onClose}>
      <div className={`df-modal-box${wide ? ' df-modal-wide' : ''}`} onClick={(e) => e.stopPropagation()}>
        <div className="df-modal-header">
          <h3>{title}</h3>
          <button type="button" className="btn-icon" onClick={onClose}>✕</button>
        </div>
        {children}
      </div>
    </div>
  );
}
