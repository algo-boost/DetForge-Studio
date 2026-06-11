import FlowGraphPanel from './FlowGraphPanel';

export default function FlowGraphDrawer({ flowId, open, onClose, mode = 'design' }) {
  if (!open) return null;

  return (
    <div className="flows-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="flows-drawer flows-drawer--wide"
        role="dialog"
        aria-label="流程图"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flows-drawer-head">
          <div>
            <h3>流程图</h3>
            <div className="flows-drawer-path">{flowId}</div>
          </div>
          <button type="button" className="btn btn-sm" onClick={onClose}>关闭</button>
        </header>
        <div className="flows-drawer-body">
          <FlowGraphPanel flowId={flowId} mode={mode} />
        </div>
      </aside>
    </div>
  );
}
