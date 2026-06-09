import { useCallback, useEffect, useState } from 'react';
import { api, toast } from '../api/client';

export default function ToolboxPage() {
  const [tools, setTools] = useState([]);
  const [stats, setStats] = useState({});
  const [selected, setSelected] = useState(null);
  const [paramsJson, setParamsJson] = useState('{}');
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  const [catalogLogs, setCatalogLogs] = useState([]);

  const load = useCallback(async () => {
    try {
      const [t, s, l] = await Promise.all([
        api.listTools(),
        api.toolStats(),
        api.catalogLogs(),
      ]);
      if (t.success) setTools(t.data || []);
      if (s.success) setStats(s.data || {});
      if (l.success) setCatalogLogs(l.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onSyncCatalog = async () => {
    setBusy(true);
    try {
      const r = await api.catalogSync();
      if (r.success) {
        toast('Catalog 同步完成', 'success');
        load();
      } else {
        toast(r.data?.error || '同步失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onExecute = async () => {
    if (!selected) return;
    setBusy(true);
    setResult(null);
    try {
      const params = JSON.parse(paramsJson || '{}');
      const r = await api.executeTool(selected.id, { params });
      setResult(r);
      if (r.success) toast('执行完成', 'success');
      else toast(r.reason || '执行失败', 'error');
      load();
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="panel active" style={{ padding: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <h2 style={{ margin: 0 }}>工具箱</h2>
          <p style={{ margin: '4px 0 0', color: 'var(--muted)' }}>
            浏览已注册 Capability / CLI / Blueprint 工具，试运行或查看 Catalog 同步状态
          </p>
        </div>
        <button type="button" className="btn primary" disabled={busy} onClick={onSyncCatalog}>
          同步 Catalog
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 16 }}>
        <div className="card" style={{ padding: 12 }}>
          <div className="sb-section-label">已注册工具 ({tools.length})</div>
          <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
            {tools.map((t) => (
              <li key={t.id}>
                <button
                  type="button"
                  className={`sb-item${selected?.id === t.id ? ' active' : ''}`}
                  style={{ width: '100%', textAlign: 'left', marginBottom: 4 }}
                  onClick={() => {
                    setSelected(t);
                    setParamsJson('{}');
                    setResult(null);
                  }}
                >
                  <div style={{ fontWeight: 600 }}>{t.label}</div>
                  <div style={{ fontSize: 11, opacity: 0.7 }}>{t.id} · {t.kind} · v{t.version || '?'}</div>
                  {stats[t.id] ? (
                    <div style={{ fontSize: 11 }}>调用 {stats[t.id]} 次</div>
                  ) : null}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div>
          {selected ? (
            <div className="card" style={{ padding: 16 }}>
              <h3 style={{ marginTop: 0 }}>{selected.label}</h3>
              <p>{selected.description || '—'}</p>
              <pre style={{ fontSize: 12, background: 'var(--bg-subtle)', padding: 12, borderRadius: 8, overflow: 'auto' }}>
                {JSON.stringify(selected.params_schema || {}, null, 2)}
              </pre>
              {selected.skill_source ? (
                <p style={{ fontSize: 12 }}>Skill 来源: <code>{selected.skill_source}</code></p>
              ) : null}
              <label style={{ display: 'block', marginTop: 12, fontSize: 13 }}>试运行参数 (JSON)</label>
              <textarea
                rows={5}
                style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
                value={paramsJson}
                onChange={(e) => setParamsJson(e.target.value)}
              />
              <button type="button" className="btn primary" style={{ marginTop: 8 }} disabled={busy} onClick={onExecute}>
                试运行
              </button>
              {result ? (
                <pre style={{ marginTop: 12, fontSize: 12, background: 'var(--bg-subtle)', padding: 12, borderRadius: 8 }}>
                  {JSON.stringify(result, null, 2)}
                </pre>
              ) : null}
            </div>
          ) : (
            <div className="card" style={{ padding: 16, color: 'var(--muted)' }}>请选择左侧工具查看详情</div>
          )}

          <div className="card" style={{ padding: 16, marginTop: 16 }}>
            <h4 style={{ marginTop: 0 }}>Catalog 同步日志</h4>
            {catalogLogs.length === 0 ? (
              <p style={{ color: 'var(--muted)' }}>暂无记录。可点击「同步 Catalog」或使用 CLI <code>iisp catalog sync</code></p>
            ) : (
              <ul style={{ fontSize: 12, paddingLeft: 18 }}>
                {catalogLogs.slice(0, 8).map((log, i) => (
                  <li key={log.id || i}>
                    {log.commit_hash || log.commit || '—'}
                    {' · '}
                    strategies={log.strategies_files}
                    {' · '}
                    {log.created_at || log.finished_at || ''}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
