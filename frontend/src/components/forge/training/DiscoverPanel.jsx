import { useEffect, useMemo, useState } from 'react';
import { api, toast } from '../../../api/client';

function itemKey(item) {
  return `${item.source_type}:${item.source_id}`;
}

export default function DiscoverPanel({ projects, selectedProject, onImported, defaultCollapsed = false }) {
  const [collapsed, setCollapsed] = useState(defaultCollapsed);
  const [url, setUrl] = useState('https://www.ai.magic-fox.com/#/datasets?approachId=598&subjectId=190');
  const [discovering, setDiscovering] = useState(false);
  const [importing, setImporting] = useState(false);
  const [result, setResult] = useState(null);
  const [tab, setTab] = useState('datasets');
  const [filter, setFilter] = useState('');
  const [selected, setSelected] = useState({});
  const [importMode, setImportMode] = useState(selectedProject ? 'existing' : 'new');
  const [projectId, setProjectId] = useState(selectedProject || '');
  const [projectName, setProjectName] = useState('');
  const [localRoot, setLocalRoot] = useState('');

  useEffect(() => {
    if (selectedProject) {
      setProjectId(selectedProject);
      setImportMode('existing');
    }
  }, [selectedProject]);

  const rows = useMemo(() => {
    if (!result) return [];
    const list = tab === 'datasets' ? (result.datasets || []) : (result.snapshots || []);
    const q = filter.trim().toLowerCase();
    if (!q) return list;
    return list.filter((x) => String(x.name || '').toLowerCase().includes(q) || String(x.source_id || x.enhance_id || '').includes(q));
  }, [result, tab, filter]);

  const selectedCount = useMemo(
    () => Object.values(selected).filter(Boolean).length,
    [selected],
  );

  const runDiscover = async () => {
    if (!url.trim()) { toast('请粘贴 Magic-Fox URL', 'error'); return; }
    setDiscovering(true);
    setSelected({});
    setCollapsed(false);
    try {
      const res = await api.forgeSyncDiscover({
        url: url.trim(),
        include_datasets: true,
        include_snapshots: true,
      });
      if (res.success) {
        setResult(res.data);
        setProjectName(`项目-${res.data.approach_id}`);
        setLocalRoot(`approach_${res.data.approach_id}`);
        toast(`发现 ${res.data.counts?.datasets || 0} 个数据集、${res.data.counts?.snapshots || 0} 个快照`);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setDiscovering(false); }
  };

  const toggleAll = (checked) => {
    const next = { ...selected };
    rows.forEach((row) => { next[itemKey(row)] = checked; });
    setSelected(next);
  };

  const toggleOne = (row) => {
    const key = itemKey(row);
    setSelected((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const runImport = async () => {
    if (!result) return;
    const items = [...(result.datasets || []), ...(result.snapshots || [])].filter((row) => selected[itemKey(row)]);
    if (!items.length) { toast('请先勾选要导入的项', 'error'); return; }
    if (importMode === 'existing' && !projectId) { toast('请选择目标项目', 'error'); return; }
    if (importMode === 'new' && !projectName.trim()) { toast('请填写新项目名称', 'error'); return; }

    setImporting(true);
    try {
      const body = {
        items,
        approach_id: result.approach_id,
        subject_id: result.subject_id,
        training_page_url: result.pages?.training,
        local_root: localRoot.trim() || undefined,
        write_db: true,
        strip_prefix: true,
      };
      if (importMode === 'existing') body.project_id = Number(projectId);
      else body.project_name = projectName.trim();

      const res = await api.forgeSyncDiscoverImport(body);
      if (res.success) {
        const d = res.data || {};
        toast(`已导入 ${d.imported_count || 0} 项（新建 ${(d.created || []).length}，更新 ${(d.updated || []).length}）`);
        onImported?.(d.project?.id);
        setSelected({});
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setImporting(false); }
  };

  return (
    <div className="forge-card sync-discover-card">
      <div className="platform-card-head">
        <div>
          <div className="forge-card-title">从 Magic-Fox URL 发现资源</div>
          <p className="sync-discover-desc">
            粘贴数据集页、训练页或增强页 URL，自动拉取该项目下全部底库数据集与训练快照。
          </p>
        </div>
        {result && (
          <button type="button" className="btn sm btn-ghost" onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? '展开' : '收起'}
          </button>
        )}
      </div>

      <div className="sync-discover-input-row">
        <input
          className="sync-discover-url"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://www.ai.magic-fox.com/#/datasets?approachId=598&subjectId=190"
        />
        <button type="button" className="btn primary" disabled={discovering} onClick={runDiscover}>
          {discovering ? '发现中…' : '发现'}
        </button>
      </div>

      {result && !collapsed && (
        <>
          <div className="sync-discover-meta">
            <span>Approach <strong>{result.approach_id}</strong></span>
            {result.subject_id != null && <span>Subject <strong>{result.subject_id}</strong></span>}
            <span>数据集 <strong>{result.counts?.datasets ?? 0}</strong></span>
            <span>快照 <strong>{result.counts?.snapshots ?? 0}</strong></span>
            {result.pages?.training && (
              <a href={result.pages.training} target="_blank" rel="noreferrer">训练页 ↗</a>
            )}
            {result.pages?.enhance && (
              <a href={result.pages.enhance} target="_blank" rel="noreferrer">增强页 ↗</a>
            )}
          </div>

          <div className="sync-discover-tabs">
            <button type="button" className={`forge-tab${tab === 'datasets' ? ' is-on' : ''}`} onClick={() => { setTab('datasets'); setFilter(''); }}>底库数据集</button>
            <button type="button" className={`forge-tab${tab === 'snapshots' ? ' is-on' : ''}`} onClick={() => { setTab('snapshots'); setFilter(''); }}>训练快照</button>
            <input
              className="sync-discover-filter"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="筛选名称或 ID…"
            />
            <button type="button" className="btn sm btn-ghost" onClick={() => toggleAll(true)}>全选本页</button>
            <button type="button" className="btn sm btn-ghost" onClick={() => toggleAll(false)}>清空</button>
          </div>

          <div className="sync-discover-table-wrap">
            <table className="forge-table sync-discover-table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={rows.length > 0 && rows.every((row) => selected[itemKey(row)])}
                      onChange={(e) => toggleAll(e.target.checked)}
                    />
                  </th>
                  <th>名称</th>
                  <th>ID</th>
                  <th>数量</th>
                  {tab === 'snapshots' && <th>底库 ID</th>}
                </tr>
              </thead>
              <tbody>
                {rows.length === 0 && (
                  <tr><td colSpan={tab === 'snapshots' ? 5 : 4} className="empty">无匹配项</td></tr>
                )}
                {rows.map((row) => {
                  const key = itemKey(row);
                  return (
                    <tr key={key}>
                      <td><input type="checkbox" checked={!!selected[key]} onChange={() => toggleOne(row)} /></td>
                      <td>{row.name}</td>
                      <td>{row.source_id ?? row.enhance_id}</td>
                      <td>{row.count ?? '—'}</td>
                      {tab === 'snapshots' && <td>{row.dataset_id ?? '—'}</td>}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          <div className="sync-discover-import">
            <div className="sync-discover-import-head">导入选中项（{selectedCount}）</div>
            <div className="forge-form-grid">
              <label>
                导入到
                <select value={importMode} onChange={(e) => setImportMode(e.target.value)}>
                  <option value="existing">已有项目</option>
                  <option value="new">新建项目</option>
                </select>
              </label>
              {importMode === 'existing' ? (
                <label>
                  目标项目
                  <select value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                    <option value="">请选择</option>
                    {projects.map((p) => (
                      <option key={p.id} value={p.id}>{p.name}</option>
                    ))}
                  </select>
                </label>
              ) : (
                <>
                  <label>新项目名称<input value={projectName} onChange={(e) => setProjectName(e.target.value)} /></label>
                  <label>本地根目录<input value={localRoot} onChange={(e) => setLocalRoot(e.target.value)} placeholder="如 approach_598" /></label>
                </>
              )}
            </div>
            <div className="forge-actions">
              <button type="button" className="btn primary" disabled={importing || !selectedCount} onClick={runImport}>
                {importing ? '导入中…' : `导入选中 ${selectedCount} 项`}
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
