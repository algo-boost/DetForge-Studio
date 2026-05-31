import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import JobsList from '../components/forge/JobsList';
import JobsTabBar from '../components/forge/jobs/JobsTabBar';
import SceneHubNav from '../components/SceneHubNav';
import { IMAGE_SOURCE_OPTIONS } from '../components/forge/jobs/jobUtils';
import { STATUS_LABEL } from '../components/forge/JobWidgets';

const JOBS_PAGE = 50;

function SurfaceCard({ title, desc, actions, children }) {
  return (
    <section className="platform-surface-card pjobs-surface-card">
      {(title || actions) && (
        <div className="platform-surface-card-head pjobs-surface-head">
          <div>
            {title && <h4>{title}</h4>}
            {desc && <p className="pjobs-surface-desc">{desc}</p>}
          </div>
          {actions && <div className="pjobs-surface-actions">{actions}</div>}
        </div>
      )}
      {children}
    </section>
  );
}

function CreatePredictForm({ models, onCreated }) {
  const [modelId, setModelId] = useState('');
  const [name, setName] = useState('');
  const [srcType, setSrcType] = useState('task');
  const [taskId, setTaskId] = useState('');
  const [dirPath, setDirPath] = useState('');
  const [paths, setPaths] = useState('');
  const [threshold, setThreshold] = useState('');
  const [device, setDevice] = useState('');
  const [maxSize, setMaxSize] = useState('');
  const [intra, setIntra] = useState(1);
  const [busy, setBusy] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const selectedModel = models.find((m) => String(m.id) === String(modelId));

  const submit = async () => {
    if (!modelId) { toast('请选择模型', 'error'); return; }
    let image_source;
    if (srcType === 'task') image_source = { type: 'task', task_id: taskId.trim() };
    else if (srcType === 'dir') image_source = { type: 'dir', path: dirPath.trim() };
    else image_source = { type: 'paths', paths: paths.split('\n').map((s) => s.trim()).filter(Boolean) };
    setBusy(true);
    try {
      const body = { model_id: Number(modelId), name: name.trim() || undefined, image_source, intra_concurrency: Number(intra) || 1 };
      if (threshold) body.threshold = Number(threshold);
      if (device) body.device = device.trim();
      if (maxSize) body.max_size = Number(maxSize);
      const res = await api.forgeEnqueuePredict(body);
      if (res.success) {
        toast(`已创建预测作业 #${res.job_id}（${res.total} 张）`);
        onCreated?.();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  if (!models.length) {
    return (
      <SurfaceCard title="新建预测作业" desc="对查询结果或本地图片目录发起单模型预测">
        <div className="pjobs-empty-state">
          <p>还没有已注册模型。</p>
          <Link to="/models" className="btn btn-sm btn-primary">前往模型页导入</Link>
        </div>
      </SurfaceCard>
    );
  }

  return (
    <SurfaceCard title="新建预测作业" desc="对查询结果或本地图片目录发起单模型预测">
      <div className="pjobs-create-steps">
        <section className="pjobs-step">
          <div className="pjobs-step-head">
            <span className="pjobs-step-num">1</span>
            <div>
              <div className="pjobs-step-title">选择模型</div>
              <div className="pjobs-step-hint">从本地注册表中选择已导入的模型</div>
            </div>
          </div>
          <div className="forge-form-grid pjobs-create-form">
            <label className="forge-span2">
              模型
              <select value={modelId} onChange={(e) => setModelId(e.target.value)}>
                <option value="">选择已注册模型…</option>
                {models.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}（{m.framework}{m.sub_type ? `/${m.sub_type}` : ''}）
                  </option>
                ))}
              </select>
            </label>
            <label>
              作业名称
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="可选，便于识别" />
            </label>
            {selectedModel && (
              <label>
                框架
                <input readOnly value={[selectedModel.framework, selectedModel.sub_type].filter(Boolean).join(' / ')} />
              </label>
            )}
          </div>
        </section>

        <section className="pjobs-step">
          <div className="pjobs-step-head">
            <span className="pjobs-step-num">2</span>
            <div>
              <div className="pjobs-step-title">图片来源</div>
              <div className="pjobs-step-hint">指定待预测图片的来源方式</div>
            </div>
          </div>
          <div className="pjobs-source-tabs">
            {IMAGE_SOURCE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                className={`pjobs-source-tab${srcType === opt.id ? ' is-active' : ''}`}
                onClick={() => setSrcType(opt.id)}
              >
                <span className="pjobs-source-tab-label">{opt.label}</span>
                <span className="pjobs-source-tab-desc">{opt.desc}</span>
              </button>
            ))}
          </div>
          <div className="forge-form-grid pjobs-create-form">
            {srcType === 'task' && (
              <label className="forge-span2">
                task_id
                <input value={taskId} onChange={(e) => setTaskId(e.target.value)} placeholder="查询页导出的 task_id" />
              </label>
            )}
            {srcType === 'dir' && (
              <label className="forge-span2">
                目录路径
                <input value={dirPath} onChange={(e) => setDirPath(e.target.value)} placeholder="/abs/path/to/images" />
              </label>
            )}
            {srcType === 'paths' && (
              <label className="forge-span2">
                图片路径（每行一个）
                <textarea rows={4} value={paths} onChange={(e) => setPaths(e.target.value)} placeholder="/path/to/img1.jpg&#10;/path/to/img2.jpg" />
              </label>
            )}
          </div>
        </section>

        <section className="pjobs-step">
          <button type="button" className="pjobs-advanced-toggle" onClick={() => setShowAdvanced((v) => !v)}>
            <span className="pjobs-step-num">3</span>
            <span>高级参数</span>
            <span className="pjobs-advanced-chevron">{showAdvanced ? '▾' : '▸'}</span>
          </button>
          {showAdvanced && (
            <div className="forge-form-grid pjobs-create-form pjobs-advanced-body">
              <label>阈值<input value={threshold} onChange={(e) => setThreshold(e.target.value)} placeholder="默认用模型设置" /></label>
              <label>设备<input value={device} onChange={(e) => setDevice(e.target.value)} placeholder="cuda:0 / cpu" /></label>
              <label>max_size<input value={maxSize} onChange={(e) => setMaxSize(e.target.value)} placeholder="1536" /></label>
              <label>任务内并发<input type="number" min={1} value={intra} onChange={(e) => setIntra(e.target.value)} /></label>
            </div>
          )}
        </section>
      </div>

      <div className="pjobs-create-footer">
        <span className="pjobs-create-summary muted">
          {selectedModel ? <>模型 <strong>{selectedModel.name}</strong></> : '请选择模型'}
          {' · '}
          {IMAGE_SOURCE_OPTIONS.find((o) => o.id === srcType)?.label || '图片来源'}
        </span>
        <button type="button" className="btn btn-primary btn-sm" onClick={submit} disabled={busy || !modelId}>
          {busy ? '提交中…' : '创建作业'}
        </button>
      </div>
    </SurfaceCard>
  );
}

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [models, setModels] = useState([]);
  const [schema, setSchema] = useState({ ready: true, database: 'detforge' });
  const [detailId, setDetailId] = useState(null);
  const [jobOffset, setJobOffset] = useState(0);
  const [jobTotal, setJobTotal] = useState(0);
  const [activeTab, setActiveTab] = useState('list');
  const timer = useRef(null);
  const jobsRef = useRef([]);

  const load = async (off = jobOffset) => {
    try {
      const [j, m] = await Promise.all([
        api.forgeJobs(`?job_type=predict&limit=${JOBS_PAGE}&offset=${off}`),
        api.forgeModels(),
      ]);
      if (j.success) { setJobs(j.data || []); jobsRef.current = j.data || []; setJobTotal(j.total || 0); setJobOffset(off); }
      if (m.success) setModels(m.data || []);
    } catch (e) { /* 静默轮询失败 */ }
  };

  const scheduleNext = () => {
    const active = jobsRef.current.some((j) => j.status === 'running' || j.status === 'pending');
    timer.current = setTimeout(async () => { await load(jobOffset); scheduleNext(); }, active ? 3000 : 12000);
  };

  const checkSchema = async () => {
    try { const s = await api.forgeSchemaStatus(); if (s.success) setSchema(s); } catch (e) { /* ignore */ }
  };

  useEffect(() => {
    checkSchema();
    load().then(scheduleNext);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const initSchema = async () => {
    try { const r = await api.forgeSchemaInit(); if (r.success) { toast('已初始化写库'); checkSchema(); } }
    catch (e) { toast(e.message, 'error'); }
  };

  const control = async (id, action) => {
    try {
      const r = await api.forgeControlJob(id, action);
      if (r.success) { toast(`#${id} → ${STATUS_LABEL[r.status] || r.status}`); load(); }
    } catch (e) { toast(e.message, 'error'); }
  };

  const stats = useMemo(() => ({
    total: jobTotal,
    active: jobs.filter((j) => j.status === 'running' || j.status === 'pending').length,
    done: jobs.filter((j) => j.status === 'done').length,
    failed: jobs.filter((j) => j.status === 'failed').length,
  }), [jobs, jobTotal]);

  const onCreated = () => {
    load(jobOffset);
    setActiveTab('list');
  };

  return (
    <div className="panel active pjobs-page">
      <SceneHubNav variant="predict" />
      <header className="pjobs-header">
        <div>
          <div className="topbar-title">预测任务</div>
          <p className="pjobs-header-desc">
            模型预测后台作业（写库 <code>{schema.database}</code>）· 批量预测请前往
            {' '}<Link to="/platform">训练平台</Link> · 数据集同步见训练平台「同步任务」
          </p>
        </div>
        <div className="pjobs-header-stats">
          <div className="pjobs-stat">
            <span className="pjobs-stat-value">{stats.total}</span>
            <span className="pjobs-stat-label">全部</span>
          </div>
          <div className="pjobs-stat pjobs-stat-active">
            <span className="pjobs-stat-value">{stats.active}</span>
            <span className="pjobs-stat-label">进行中</span>
          </div>
          <div className="pjobs-stat pjobs-stat-ok">
            <span className="pjobs-stat-value">{stats.done}</span>
            <span className="pjobs-stat-label">已完成</span>
          </div>
          <div className="pjobs-stat pjobs-stat-err">
            <span className="pjobs-stat-value">{stats.failed}</span>
            <span className="pjobs-stat-label">失败</span>
          </div>
        </div>
      </header>

      {!schema.ready && (
        <div className="pjobs-schema-banner">
          <span>写库 <code>{schema.database}</code> 尚未初始化，预测结果无法写入。</span>
          <button type="button" className="btn btn-sm btn-primary" onClick={initSchema}>立即建库建表</button>
        </div>
      )}

      <JobsTabBar
        activeTab={activeTab}
        onTabChange={setActiveTab}
        counts={{ list: stats.active || undefined }}
      />

      <div className="pjobs-workspace">
        {activeTab === 'list' && (
          <SurfaceCard
            title="预测作业列表"
            desc="查看进度、日志与预测结果，支持暂停 / 继续 / 重试"
            actions={
              <button type="button" className="btn btn-sm btn-ghost" onClick={() => load(jobOffset)}>刷新</button>
            }
          >
            <JobsList
              jobs={jobs}
              jobTotal={jobTotal}
              jobOffset={jobOffset}
              pageSize={JOBS_PAGE}
              onPageChange={load}
              detailId={detailId}
              setDetailId={setDetailId}
              onControl={control}
              emptyText="暂无预测作业。可在「新建预测」创建，或从训练平台批量提交。"
            />
          </SurfaceCard>
        )}

        {activeTab === 'create' && (
          <CreatePredictForm models={models} onCreated={onCreated} />
        )}
      </div>
    </div>
  );
}
