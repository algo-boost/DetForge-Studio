import { useCallback, useEffect, useState } from 'react';
import { api, openSampleGalleryWhenReady, toast } from '../../../api/client';
import { buildPlatformDataViewUrl } from './platformUtils';

function ProjectForm({ project, onSaved, onCancel }) {
  const [form, setForm] = useState({
    id: project?.id,
    name: project?.name || '',
    approach_id: project?.approach_id ?? '',
    training_page_url: project?.training_page_url || '',
    local_root: project?.local_root || '',
    note: project?.note || '',
    enabled: project?.enabled ?? 1,
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.name.trim()) { toast('请填写项目名称', 'error'); return; }
    setBusy(true);
    try {
      const body = {
        ...form,
        approach_id: form.approach_id === '' ? null : Number(form.approach_id),
      };
      const res = await api.forgeSyncSaveProject(body);
      if (res.success) {
        toast(project?.id ? '项目已更新' : '项目已创建');
        onSaved?.(res.data);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <div className="forge-card platform-inline-form">
      <div className="forge-card-title">{project?.id ? '编辑项目' : '新建项目'}</div>
      <div className="forge-form-grid">
        <label>项目名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>Approach ID<input value={form.approach_id} onChange={(e) => setForm({ ...form, approach_id: e.target.value })} placeholder="如 598" /></label>
        <label className="forge-span2">训练页 URL<input value={form.training_page_url} onChange={(e) => setForm({ ...form, training_page_url: e.target.value })} placeholder="#/training?approachId=…" /></label>
        <label className="forge-span2">本地根目录（可选）<input value={form.local_root} onChange={(e) => setForm({ ...form, local_root: e.target.value })} placeholder="留空则用 config.dataset_sync_root" /></label>
        <label className="forge-span2">备注<input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></label>
      </div>
      <div className="forge-actions">
        <button type="button" className="btn primary" disabled={busy} onClick={submit}>{busy ? '保存中…' : '保存'}</button>
        {onCancel && <button type="button" className="btn" onClick={onCancel}>取消</button>}
      </div>
    </div>
  );
}

function DatasetForm({ projectId, dataset, onSaved, onCancel }) {
  const [form, setForm] = useState({
    id: dataset?.id,
    project_id: projectId,
    name: dataset?.name || '',
    source_type: dataset?.source_type || 'dataset',
    source_id: dataset?.source_id ?? '',
    data_view_url: dataset?.data_view_url || '',
    local_dir: dataset?.local_dir || '',
    split_subdirs: !!dataset?.split_subdirs,
    strip_prefix: dataset?.strip_prefix !== 0,
    write_db: dataset != null ? !!dataset.write_db : true,
    enabled: dataset?.enabled ?? 1,
  });
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!form.name.trim() || !form.source_id || !form.local_dir.trim()) {
      toast('请填写名称、线上 ID 与本地目录', 'error');
      return;
    }
    setBusy(true);
    try {
      const res = await api.forgeSyncSaveDataset(form);
      if (res.success) {
        toast(dataset?.id ? '数据集已更新' : '数据集已添加');
        onSaved?.(res.data);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <div className="forge-card platform-inline-form">
      <div className="forge-card-title">{dataset?.id ? '编辑数据集' : '添加数据集'}</div>
      <div className="forge-form-grid">
        <label>名称<input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label>
        <label>来源类型
          <select value={form.source_type} onChange={(e) => setForm({ ...form, source_type: e.target.value })}>
            <option value="dataset">底库 dataset_id</option>
            <option value="snapshot">训练快照 generate_id</option>
          </select>
        </label>
        <label>线上 ID<input value={form.source_id} onChange={(e) => setForm({ ...form, source_id: e.target.value })} placeholder="dataset_id 或 generate_id" /></label>
        <label>本地子目录<input value={form.local_dir} onChange={(e) => setForm({ ...form, local_dir: e.target.value })} placeholder="如 yfmb/train_v63" /></label>
        <label className="forge-span2">dataView URL（可选）<input value={form.data_view_url} onChange={(e) => setForm({ ...form, data_view_url: e.target.value })} /></label>
        <label><input type="checkbox" checked={form.strip_prefix} onChange={(e) => setForm({ ...form, strip_prefix: e.target.checked })} /> 去掉文件名前缀</label>
        <label><input type="checkbox" checked={form.split_subdirs} onChange={(e) => setForm({ ...form, split_subdirs: e.target.checked })} /> train/valid/test 子目录</label>
        <label><input type="checkbox" checked={form.write_db} onChange={(e) => setForm({ ...form, write_db: e.target.checked })} /> 标注写入数据库</label>
      </div>
      <div className="forge-actions">
        <button type="button" className="btn primary" disabled={busy} onClick={submit}>{busy ? '保存中…' : '保存'}</button>
        {onCancel && <button type="button" className="btn" onClick={onCancel}>取消</button>}
      </div>
    </div>
  );
}

function DatasetRow({ ds, project, onRefresh, onSyncStarted, onPredict, onEdit, onGoJobs, onGoTrace }) {
  const [status, setStatus] = useState(null);
  const [syncing, setSyncing] = useState(false);
  const [openingViz, setOpeningViz] = useState(false);
  const [savingWriteDb, setSavingWriteDb] = useState(false);

  const loadStatus = useCallback(async () => {
    try {
      const res = await api.forgeSyncDatasetStatus(ds.id);
      if (res.success) setStatus(res.data);
    } catch { /* ignore */ }
  }, [ds.id]);

  useEffect(() => { loadStatus(); }, [loadStatus]);

  const platformUrl = buildPlatformDataViewUrl(ds, project);
  const localPct = status?.remote_count
    ? Math.min(100, Math.round((status.local_count / status.remote_count) * 100))
    : null;

  const openViz = async () => {
    if (!status?.has_coco) {
      toast('请先同步数据集以生成 COCO 标注', 'error');
      return;
    }
    setOpeningViz(true);
    try {
      await openSampleGalleryWhenReady(() => api.forgeSyncOpenViz(ds.id));
      toast('样本图库已打开');
    } catch (e) { toast(e.message, 'error'); }
    finally { setOpeningViz(false); }
  };

  const runSync = async () => {
    setSyncing(true);
    try {
      const res = await api.forgeSyncRun(ds.id, { async: true });
      if (res.success) {
        toast(`已创建同步作业 #${res.job_id}`);
        onRefresh?.();
        onSyncStarted?.();
        onGoJobs?.();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setSyncing(false); }
  };

  const remove = async () => {
    if (!window.confirm(
      `移除数据集「${ds.name}」的同步配置？\n\n`
      + '仅删除本工具中的同步记录，不会删除 Magic-Fox 平台上的远程数据集，也不会删除已下载的本地文件。',
    )) return;
    try {
      await api.forgeSyncDeleteDataset(ds.id);
      toast('已删除');
      onRefresh?.();
    } catch (e) { toast(e.message, 'error'); }
  };

  const toggleWriteDb = async (checked) => {
    setSavingWriteDb(true);
    try {
      const res = await api.forgeSyncSaveDataset({ ...ds, write_db: checked });
      if (res.success) {
        toast(checked ? '已开启写库' : '已关闭写库');
        onRefresh?.();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setSavingWriteDb(false); }
  };

  return (
    <tr className="platform-dataset-row">
      <td>
        <div className="platform-dataset-name-cell">
          {platformUrl ? (
            <a className="sync-dataset-link" href={platformUrl} target="_blank" rel="noreferrer" title="在 Magic-Fox 打开">
              {ds.name}
            </a>
          ) : (
            <span>{ds.name}</span>
          )}
          <span className={`platform-dataset-type platform-dataset-type-${ds.source_type}`}>
            {ds.source_type === 'snapshot' ? '快照' : '底库'} #{ds.source_id}
          </span>
        </div>
      </td>
      <td><code className="platform-dataset-path">{ds.local_dir}</code></td>
      <td>
        <div className="platform-sync-progress">
          <span>{status ? `${status.local_count} / ${status.remote_count || ds.remote_count || '?'}` : '…'}</span>
          {localPct != null && (
            <div className="platform-sync-bar" title={`本地 ${localPct}%`}>
              <div className="platform-sync-bar-fill" style={{ width: `${localPct}%` }} />
            </div>
          )}
        </div>
      </td>
      <td className="platform-dataset-write-db">
        <label className="platform-write-db-check" title="标注写入数据库（SN/款型溯源）">
          <input
            type="checkbox"
            checked={!!ds.write_db}
            disabled={savingWriteDb}
            onChange={(e) => toggleWriteDb(e.target.checked)}
          />
          <span>{ds.write_db ? '是' : '否'}</span>
        </label>
      </td>
      <td className="platform-dataset-time">{ds.last_sync_at ? String(ds.last_sync_at).slice(0, 16) : '—'}</td>
      <td className="forge-row-actions platform-dataset-actions">
        <button type="button" className="btn sm primary" disabled={syncing} onClick={runSync}>
          {syncing ? '…' : '同步'}
        </button>
        <button type="button" className="btn sm" onClick={() => onPredict?.(ds.id)} disabled={!status?.local_count}>预测</button>
        <button type="button" className="btn sm btn-ghost" disabled={openingViz || !status?.has_coco} onClick={openViz}>看图</button>
        {onGoTrace && (
          <button type="button" className="btn sm btn-ghost" disabled={!ds.write_db} onClick={() => onGoTrace?.()} title={ds.write_db ? '' : '请先勾选写库'}>溯源</button>
        )}
        <button type="button" className="btn sm btn-ghost" onClick={() => onEdit?.(ds)}>编辑</button>
        <button type="button" className="btn sm btn-ghost" onClick={() => onGoJobs?.()}>任务</button>
        <button type="button" className="btn sm btn-ghost danger" onClick={remove}>移除</button>
      </td>
    </tr>
  );
}

export default function DatasetSection({
  project,
  projectId,
  datasets,
  onRefresh,
  onSyncStarted,
  onPredict,
  onGoJobs,
  onGoDiscover,
  onGoTrace,
}) {
  const [showDatasetForm, setShowDatasetForm] = useState(false);
  const [editingDataset, setEditingDataset] = useState(null);
  const [syncingAll, setSyncingAll] = useState(false);

  const syncAll = async () => {
    if (!datasets.length) return;
    setSyncingAll(true);
    try {
      let n = 0;
      for (const ds of datasets) {
        const res = await api.forgeSyncRun(ds.id, { async: true });
        if (res.success) n += 1;
      }
      toast(`已提交 ${n} 个同步任务`);
      onRefresh?.();
      onSyncStarted?.();
      onGoJobs?.();
    } catch (e) { toast(e.message, 'error'); }
    finally { setSyncingAll(false); }
  };

  return (
    <div className="platform-datasets-section">
      <div className="platform-section-toolbar platform-surface-card platform-section-toolbar-card">
        <div>
          <h3 className="platform-section-title">本地数据集</h3>
          <p className="platform-section-desc">管理同步配置，拉取 Magic-Fox 图片与 COCO 到本地</p>
        </div>
        <div className="platform-section-toolbar-actions">
          <button type="button" className="btn sm" disabled={syncingAll || !datasets.length} onClick={syncAll}>
            {syncingAll ? '提交中…' : '全部同步'}
          </button>
          <button type="button" className="btn sm primary" onClick={() => { setEditingDataset(null); setShowDatasetForm(true); }}>
            添加数据集
          </button>
        </div>
      </div>

      {showDatasetForm && (
        <DatasetForm
          projectId={projectId}
          dataset={editingDataset}
          onSaved={() => { setShowDatasetForm(false); setEditingDataset(null); onRefresh?.(); }}
          onCancel={() => { setShowDatasetForm(false); setEditingDataset(null); }}
        />
      )}

      <div className="platform-surface-card platform-dataset-table-card">
        <table className="forge-table platform-dataset-table">
          <thead>
            <tr>
              <th>名称 / 来源</th>
              <th>本地目录</th>
              <th>本地 / 线上</th>
              <th>写库</th>
              <th>上次同步</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {datasets.length === 0 && (
              <tr>
                <td colSpan={6} className="platform-empty-cell">
                  <p>暂无数据集</p>
                  <div className="platform-empty-actions">
                    <button type="button" className="btn sm primary" onClick={() => setShowDatasetForm(true)}>手动添加</button>
                    {onGoDiscover && (
                      <button type="button" className="btn sm" onClick={onGoDiscover}>URL 发现导入</button>
                    )}
                  </div>
                </td>
              </tr>
            )}
            {datasets.map((ds) => (
              <DatasetRow
                key={ds.id}
                ds={ds}
                project={project}
                onRefresh={onRefresh}
                onSyncStarted={onSyncStarted}
                onPredict={onPredict}
                onEdit={(d) => { setEditingDataset(d); setShowDatasetForm(true); }}
                onGoJobs={onGoJobs}
                onGoTrace={onGoTrace}
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// fix reference - DatasetSection uses projects incorrectly in empty state, remove that
export { ProjectForm };
