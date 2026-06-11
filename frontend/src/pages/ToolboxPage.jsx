import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import ToolCard from '../components/toolbox/ToolCard';
import ToolDetailPanel from '../components/toolbox/ToolDetailPanel';

export default function ToolboxPage() {
  const [tab, setTab] = useState('browse');
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

  const sortedTools = useMemo(
    () => [...tools].sort((a, b) => String(a.label || a.id).localeCompare(String(b.label || b.id))),
    [tools],
  );

  const selectTool = (tool) => {
    setSelected(tool);
    setParamsJson('{}');
    setResult(null);
  };

  return (
    <div className="panel active toolbox-page">
      <SceneHubNav variant="platform" />
      <header className="toolbox-header">
        <div>
          <h1 className="toolbox-title">工具箱</h1>
          <p className="toolbox-desc">
            浏览已注册 Capability / CLI / Blueprint；开发者模式可 JSON 试运行
          </p>
        </div>
        <button type="button" className="btn btn-primary" disabled={busy} onClick={onSyncCatalog}>
          同步 Catalog
        </button>
      </header>

      <div className="toolbox-tabs">
        {[
          ['browse', '浏览'],
          ['developer', '开发者'],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`toolbox-tab${tab === id ? ' is-active' : ''}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'browse' && (
        <div className="toolbox-browse-layout">
          <div>
            {!sortedTools.length ? (
              <div className="panel toolbox-empty">暂无已注册工具</div>
            ) : (
              <div className="toolbox-card-grid">
                {sortedTools.map((t) => (
                  <ToolCard
                    key={t.id}
                    tool={t}
                    stats={stats}
                    selected={selected?.id === t.id}
                    onSelect={selectTool}
                  />
                ))}
              </div>
            )}
          </div>
          <ToolDetailPanel tool={selected} mode="browse" />
        </div>
      )}

      {tab === 'developer' && (
        <div className="toolbox-dev-layout">
          <div className="panel" style={{ padding: 12 }}>
            <div className="sb-section-label">工具 ({tools.length})</div>
            <ul className="toolbox-dev-list">
              {sortedTools.map((t) => (
                <li key={t.id}>
                  <button
                    type="button"
                    className={`toolbox-dev-item${selected?.id === t.id ? ' is-selected' : ''}`}
                    onClick={() => selectTool(t)}
                  >
                    <div style={{ fontWeight: 600 }}>{t.label}</div>
                    <div style={{ fontSize: 11, opacity: 0.7 }}>{t.id}</div>
                  </button>
                </li>
              ))}
            </ul>
          </div>

          <div>
            {selected ? (
              <>
                <ToolDetailPanel tool={selected} mode="developer" />
                <div className="panel" style={{ padding: 16, marginTop: 16 }}>
                  <h4 style={{ marginTop: 0 }}>JSON 试运行</h4>
                  <textarea
                    rows={5}
                    style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
                    value={paramsJson}
                    onChange={(e) => setParamsJson(e.target.value)}
                  />
                  <button
                    type="button"
                    className="btn btn-primary"
                    style={{ marginTop: 8 }}
                    disabled={busy}
                    onClick={onExecute}
                  >
                    试运行
                  </button>
                  {result && (
                    <pre className="toolbox-result-pre" style={{ marginTop: 12 }}>
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  )}
                </div>
              </>
            ) : (
              <div className="panel toolbox-empty">请选择工具</div>
            )}

            <div className="panel" style={{ padding: 16, marginTop: 16 }}>
              <h4 style={{ marginTop: 0 }}>Catalog 同步日志</h4>
              {catalogLogs.length === 0 ? (
                <p className="toolbox-desc">
                  暂无记录。可点击「同步 Catalog」或使用 CLI
                  {' '}
                  <code>iisp catalog sync</code>
                </p>
              ) : (
                <ul className="toolbox-log-list">
                  {catalogLogs.slice(0, 10).map((log, i) => (
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
      )}
    </div>
  );
}
