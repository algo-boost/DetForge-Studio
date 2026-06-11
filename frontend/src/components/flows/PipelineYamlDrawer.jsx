import { useEffect, useState } from 'react';
import { api, toast } from '../../api/client';

export default function PipelineYamlDrawer({ flowId, open, onClose }) {
  const [yaml, setYaml] = useState('');
  const [path, setPath] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !flowId) return undefined;
    let cancelled = false;
    setLoading(true);
    api.flowPipelineYaml(flowId).then((r) => {
      if (cancelled) return;
      if (r.success) {
        setYaml(r.data?.yaml || '');
        setPath(r.data?.path || '');
      } else {
        toast(r.error || '加载 YAML 失败', 'error');
      }
    }).catch((e) => {
      if (!cancelled) toast(String(e.message || e), 'error');
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [open, flowId]);

  if (!open) return null;

  return (
    <div className="flows-drawer-backdrop" role="presentation" onClick={onClose}>
      <aside
        className="flows-drawer"
        role="dialog"
        aria-label="Pipeline YAML"
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flows-drawer-head">
          <div>
            <h3>{flowId}</h3>
            {path && <div className="flows-drawer-path">{path}</div>}
          </div>
          <button type="button" className="btn btn-sm" onClick={onClose}>关闭</button>
        </header>
        {loading ? (
          <p className="flows-muted">加载中…</p>
        ) : (
          <pre className="flows-yaml-pre">{yaml || '（空）'}</pre>
        )}
      </aside>
    </div>
  );
}
