import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import ModelsTabBar from '../components/models/ModelsTabBar';
import SceneHubNav from '../components/SceneHubNav';
import { SOURCE_LABEL, SOURCE_PILL_CLASS } from '../components/models/modelsUtils';

function SurfaceCard({ title, desc, actions, children }) {
  return (
    <section className="platform-surface-card models-surface-card">
      {(title || actions) && (
        <div className="platform-surface-card-head models-surface-head">
          <div>
            {title && <h4>{title}</h4>}
            {desc && <p className="models-surface-desc">{desc}</p>}
          </div>
          {actions && <div className="models-surface-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

function SourcePill({ source }) {
  const cls = SOURCE_PILL_CLASS[source] || 'models-pill';
  return <span className={cls}>{SOURCE_LABEL[source] || source || '—'}</span>;
}

function ManualRegister({ onDone }) {
  const [name, setName] = useState('');
  const [framework, setFramework] = useState('hq_det');
  const [subType, setSubType] = useState('');
  const [path, setPath] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    if (!path.trim()) { toast('请填写权重路径', 'error'); return; }
    setBusy(true);
    try {
      const r = await api.forgeCreateModel({
        name: name.trim() || undefined, framework, sub_type: subType.trim() || undefined,
        checkpoint_path: path.trim(), source: 'manual',
      });
      if (r.success) { toast('已登记模型'); setName(''); setPath(''); setSubType(''); onDone?.(); }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  return (
    <SurfaceCard title="手动登记权重" desc="填写本地 .pt / .pth 绝对路径，登记到注册表供本地预测任务使用">
      <div className="forge-form-grid models-register-form">
        <label>名称<input value={name} onChange={(e) => setName(e.target.value)} placeholder="可选，便于识别" /></label>
        <label>框架
          <select value={framework} onChange={(e) => setFramework(e.target.value)}>
            <option value="hq_det">hq_det</option>
            <option value="dino">dino (ml_backend)</option>
          </select>
        </label>
        <label>子类型<input value={subType} onChange={(e) => setSubType(e.target.value)} placeholder="rtdetr / yolo / dino…（留空自动探测）" /></label>
        <label className="forge-span2">权重路径<input value={path} onChange={(e) => setPath(e.target.value)} placeholder="模型 .pt / .pth 绝对路径" /></label>
      </div>
      <div className="models-action-bar">
        <button type="button" className="btn btn-sm btn-primary" onClick={submit} disabled={busy}>{busy ? '登记中…' : '登记到注册表'}</button>
      </div>
    </SurfaceCard>
  );
}

function EmptyTable({ loading, text, action }) {
  return (
    <div className="models-empty-state">
      <p>{loading ? '加载中…' : text}</p>
      {action}
    </div>
  );
}

export default function ModelsPage() {
  const [deploy, setDeploy] = useState([]);
  const [train, setTrain] = useState([]);
  const [registry, setRegistry] = useState([]);
  const [platformModels, setPlatformModels] = useState([]);
  const [platformMeta, setPlatformMeta] = useState(null);
  const [projects, setProjects] = useState([]);
  const [projectId, setProjectId] = useState('');
  const [tab, setTab] = useState('registry');
  const [platformRoot, setPlatformRoot] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncingPlatform, setSyncingPlatform] = useState(false);

  const loadCore = async () => {
    let approachId = '';
    const cfg = await api.getConfig();
    if (cfg.success) {
      approachId = cfg.config?.defect_approach_id || '';
      const root = cfg.config?.platform_root || cfg.config?.img_base_path || '';
      if (root) setPlatformRoot(root);
    }
    const deployQs = approachId ? `?approach_id=${approachId}&limit=200` : '?limit=200';
    const [d, t, r] = await Promise.all([
      api.getDeployedModels(deployQs),
      api.getTrainingModels(deployQs),
      api.forgeModels(),
    ]);
    if (d.success) setDeploy(d.data || d.models || []);
    if (t.success) setTrain(t.data || t.models || []);
    if (r.success) setRegistry(r.data || []);
  };

  const loadProjects = async () => {
    try {
      const res = await api.forgeSyncProjects();
      if (res.success) {
        const list = res.data || [];
        setProjects(list);
        if (!projectId && list.length) setProjectId(String(list[0].id));
        else if (projectId && !list.some((p) => String(p.id) === String(projectId)) && list.length) {
          setProjectId(String(list[0].id));
        }
      }
    } catch { /* ignore */ }
  };

  const loadPlatformModels = async (pid = projectId, force = false) => {
    if (!pid) { setPlatformModels([]); setPlatformMeta(null); return; }
    setSyncingPlatform(true);
    try {
      const res = force
        ? await api.forgeSyncTrainModels(Number(pid), true)
        : await api.getTrainingModels(`?project_id=${pid}&limit=500`);
      if (res.success) {
        setPlatformModels(res.models || res.data || []);
        setPlatformMeta(res.meta || { count: (res.models || []).length, synced_count: res.synced_count, source: res.meta?.source || 'platform_cache' });
      }
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSyncingPlatform(false);
    }
  };

  const load = async () => {
    setLoading(true);
    try { await loadCore(); } finally { setLoading(false); }
  };

  useEffect(() => { load(); loadProjects(); }, []);

  useEffect(() => {
    if (tab === 'platform' && projectId) loadPlatformModels(projectId, false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, projectId]);

  const copy = (text) => { navigator.clipboard?.writeText(text || ''); toast('已复制'); };

  const importDeploy = async (m) => {
    if (!m.full_path) { toast('该模型无法解析完整路径', 'error'); return; }
    try {
      const r = await api.forgeCreateModel({
        name: m.deploy_name || m.name, checkpoint_path: m.full_path, model_type: m.model_type,
        labels: m.labels, source: 'modeldeploy', source_ref: String(m.id), approach_id: m.approach_id,
      });
      if (r.success) { toast('已导入到注册表'); load(); }
    } catch (e) { toast(e.message, 'error'); }
  };

  const importTrain = async (m) => {
    const path = m.full_path || m.hint_path || m.path;
    if (!path) { toast('无参考路径，请手动登记', 'error'); return; }
    try {
      const r = await api.forgeCreateModel({
        name: m.model_name || m.name, checkpoint_path: path, model_type: m.model_type,
        labels: m.labels, source: 'modeltrainconfig', source_ref: String(m.id),
        approach_id: m.approach_id,
      });
      if (r.success) { toast('已导入（请核对路径）'); load(); }
    } catch (e) { toast(e.message, 'error'); }
  };

  const importAllTrain = async () => {
    const cfg = await api.getConfig();
    const aid = cfg.config?.defect_approach_id;
    if (!aid) { toast('未配置 defect_approach_id', 'error'); return; }
    try {
      const r = await api.forgeImportAllPlatformModels({
        approach_id: aid, include_deploy: false, include_train: true,
      });
      if (r.success) {
        toast(`已导入 ${r.imported_count} 个训练模型${r.skipped_count ? `，跳过 ${r.skipped_count} 个` : ''}`);
        load();
      }
    } catch (e) { toast(e.message, 'error'); }
  };

  const del = async (id) => {
    try { const r = await api.forgeDeleteModel(id); if (r.success) { toast('已删除'); load(); } }
    catch (e) { toast(e.message, 'error'); }
  };

  const toggle = async (m) => {
    try { const r = await api.forgeSetModelEnabled(m.id, !m.enabled); if (r.success) load(); }
    catch (e) { toast(e.message, 'error'); }
  };

  const checkHealth = async (m) => {
    toast(`正在加载校验「${m.name}」…`);
    try {
      const r = await api.forgeModelHealth(m.id);
      if (r.ok) toast(`模型可加载（${r.framework} @ ${r.device}）`);
      else toast(`加载失败：${r.error || '未知错误'}`, 'error');
    } catch (e) { toast(e.message, 'error'); }
  };

  const enabledCount = useMemo(() => registry.filter((m) => m.enabled).length, [registry]);
  const tabCounts = {
    registry: registry.length,
    platform: platformModels.length || undefined,
    deploy: deploy.length,
    train: train.length,
  };

  const tabEmptyText = {
    registry: '注册表为空。可手动登记，或从「部署模型 / 训练配置」导入本地权重。',
    platform: projects.length
      ? '该平台项目尚无缓存模型。点击「从 Magic-Fox 同步」拉取训练页列表。'
      : '请先在训练平台创建并同步项目，再查看线上训练模型。',
    deploy: '无部署模型数据，请检查数据库连接与 Approach 配置。',
    train: '无训练配置数据，请检查数据库连接与 Approach 配置。',
  };

  const selectedProject = projects.find((p) => String(p.id) === String(projectId));

  const renderTableBody = () => {
    if (tab === 'platform') {
      if (!projects.length) {
        return (
          <EmptyTable
            loading={loading}
            text={tabEmptyText.platform}
            action={<Link to="/training" className="btn btn-sm btn-primary">前往训练平台</Link>}
          />
        );
      }
      if (!platformModels.length) {
        return (
          <EmptyTable
            loading={syncingPlatform}
            text={tabEmptyText.platform}
            action={
              <button type="button" className="btn btn-sm btn-primary" disabled={syncingPlatform || !projectId} onClick={() => loadPlatformModels(projectId, true)}>
                {syncingPlatform ? '同步中…' : '从 Magic-Fox 同步'}
              </button>
            }
          />
        );
      }
      return (
        <div className="models-table-wrap">
          <table className="models-table models-table-pro">
            <thead>
              <tr>
                <th>train_id</th><th>模型名称</th><th>类型</th><th>进度</th><th>创建时间</th><th>数据集快照</th><th>来源</th>
              </tr>
            </thead>
            <tbody>
              {platformModels.map((m) => (
                <tr key={m.train_id || m.id}>
                  <td className="models-id">#{m.train_id || m.id}</td>
                  <td className="models-name">{m.model_name || m.name || '—'}</td>
                  <td><span className="models-tag">{m.model_type || '—'}</span></td>
                  <td>{m.train_progress || '—'}</td>
                  <td>{m.c_time || '—'}</td>
                  <td className="models-path-cell"><span className="models-path-note">{m.snapshot_note || m.remark || '—'}</span></td>
                  <td><SourcePill source="platform" /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    const rows = tab === 'deploy' ? deploy : tab === 'train' ? train : registry;
    if (!rows.length) return <EmptyTable loading={loading} text={tabEmptyText[tab]} />;

    return (
      <div className="models-table-wrap">
        <table className="models-table models-table-pro">
          <thead>
            <tr>
              {tab === 'deploy' && <><th>部署名</th><th>类型</th><th>完整路径</th><th>操作</th></>}
              {tab === 'train' && <><th>名称</th><th>类型</th><th>参考路径</th><th>操作</th></>}
              {tab === 'registry' && <><th>名称</th><th>框架</th><th>路径</th><th>来源</th><th>状态</th><th>操作</th></>}
            </tr>
          </thead>
          <tbody>
            {tab === 'deploy' && deploy.map((m, i) => (
              <tr key={m.id || i}>
                <td className="models-name">{m.deploy_name || m.name}</td>
                <td><span className="models-tag">{m.model_type || '—'}</span></td>
                <td className="models-path-cell">
                  <code className="models-path">{m.full_path || '—'}</code>
                  {m.full_path && <button type="button" className="models-copy-btn" onClick={() => copy(m.full_path)}>复制</button>}
                </td>
                <td><button type="button" className="btn btn-sm btn-primary" onClick={() => importDeploy(m)}>导入</button></td>
              </tr>
            ))}
            {tab === 'train' && train.map((m, i) => (
              <tr key={m.id || i}>
                <td className="models-name">{m.model_name || m.name || m.id}</td>
                <td><span className="models-tag">{m.model_type || '—'}</span></td>
                <td className="models-path-cell">
                  <code className="models-path">{m.full_path || m.hint_path || m.path || '—'}</code>
                  {m.path_resolvable === false && <span className="models-pill models-pill-err">文件不存在</span>}
                </td>
                <td>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => importTrain(m)} disabled={m.path_resolvable === false}>导入</button>
                </td>
              </tr>
            ))}
            {tab === 'registry' && registry.map((m) => (
              <tr key={m.id}>
                <td className="models-name">{m.name}</td>
                <td><span className="models-tag">{m.framework}{m.sub_type ? `/${m.sub_type}` : ''}</span></td>
                <td className="models-path-cell"><code className="models-path">{m.checkpoint_path}</code></td>
                <td><SourcePill source={m.source} /></td>
                <td>
                  <button type="button" className={`models-toggle${m.enabled ? ' is-on' : ''}`} onClick={() => toggle(m)} aria-pressed={!!m.enabled}>
                    {m.enabled ? '已启用' : '已禁用'}
                  </button>
                </td>
                <td className="models-row-actions">
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => checkHealth(m)}>健康检查</button>
                  <button type="button" className="btn btn-sm btn-ghost models-action-danger" onClick={() => del(m.id)}>删除</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  const tableTitle = {
    registry: '注册表模型',
    platform: '训练平台模型',
    deploy: '部署模型列表',
    train: '训练配置列表',
  }[tab];

  const tableDesc = {
    registry: '本地权重注册表，用于本地加载预测',
    platform: '从 Magic-Fox 训练页同步的模型列表，预测走线上 model_validation API（无需导入权重）',
    deploy: '从 vision_backend 读取部署权重，可导入注册表做本地预测',
    train: '从 modeltrainconfig 读取训练权重参考路径，可导入注册表',
  }[tab];

  return (
    <div className="panel active models-page">
      <SceneHubNav variant="predict" />
      <header className="models-header">
        <div>
          <div className="topbar-title">模型</div>
          <p className="models-header-desc">
            本地注册表 · 训练平台线上模型 · DB 部署/训练权重 · 供
            {' '}<Link to="/jobs">预测任务</Link> 与 <Link to="/training">训练平台</Link> 使用
          </p>
        </div>
        <div className="models-header-stats">
          <div className="models-stat">
            <span className="models-stat-value">{registry.length}</span>
            <span className="models-stat-label">注册表</span>
          </div>
          <div className="models-stat models-stat-ok">
            <span className="models-stat-value">{enabledCount}</span>
            <span className="models-stat-label">已启用</span>
          </div>
          <div className="models-stat models-stat-active">
            <span className="models-stat-value">{platformModels.length}</span>
            <span className="models-stat-label">平台缓存</span>
          </div>
          <div className="models-stat">
            <span className="models-stat-value">{deploy.length}</span>
            <span className="models-stat-label">部署</span>
          </div>
        </div>
      </header>

      {platformRoot && (
        <div className="models-platform-banner">
          <span className="models-platform-label">平台根路径</span>
          <code>{platformRoot}</code>
        </div>
      )}

      <ModelsTabBar activeTab={tab} onTabChange={setTab} counts={tabCounts} />

      <div className="models-workspace">
        {tab === 'registry' && <ManualRegister onDone={load} />}

        {tab === 'platform' && (
          <SurfaceCard
            title="训练平台项目"
            desc="选择已同步的 Magic-Fox 项目，查看或刷新该平台上的训练模型列表"
            actions={
              <>
                <button type="button" className="btn btn-sm btn-ghost" onClick={loadProjects}>刷新项目</button>
                <button type="button" className="btn btn-sm btn-primary" disabled={syncingPlatform || !projectId} onClick={() => loadPlatformModels(projectId, true)}>
                  {syncingPlatform ? '同步中…' : '从 Magic-Fox 同步'}
                </button>
                <Link className="btn btn-sm btn-ghost" to="/training">训练平台</Link>
              </>
            }
          >
            <div className="models-platform-toolbar">
              <label className="models-platform-select">
                项目
                <select value={projectId} onChange={(e) => setProjectId(e.target.value)} disabled={!projects.length}>
                  {!projects.length && <option value="">暂无项目 — 请先在训练平台创建</option>}
                  {projects.map((p) => (
                    <option key={p.id} value={p.id}>{p.name}（approach {p.approach_id}）</option>
                  ))}
                </select>
              </label>
              {selectedProject && (
                <div className="models-platform-meta muted">
                  {platformMeta?.synced_count != null && <>已缓存 {platformMeta.synced_count} 个 · </>}
                  当前 {platformModels.length} 条
                  {platformMeta?.source && <> · 来源 {platformMeta.source}</>}
                </div>
              )}
            </div>
            <p className="models-platform-hint">
              训练平台模型<strong>无需导入权重</strong>，在训练平台「预测」工作区勾选后走 Magic-Fox 线上 API 批量验证。
            </p>
          </SurfaceCard>
        )}

        {tab === 'train' && (
          <SurfaceCard
            title="批量导入（DB 训练配置）"
            desc="将 vision_backend 中当前 Approach 的训练配置导入本地注册表"
            actions={<button type="button" className="btn btn-sm btn-primary" onClick={importAllTrain}>全部导入</button>}
          />
        )}

        <SurfaceCard
          title={tableTitle}
          desc={tableDesc}
          actions={<button type="button" className="btn btn-sm btn-ghost" onClick={load} disabled={loading}>刷新</button>}
        >
          {renderTableBody()}
        </SurfaceCard>
      </div>
    </div>
  );
}
