import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../../api/client';
import { showErrorModal, showResultModal } from '../../lib/feedbackModal';
import {
  registryMatchesApproaches,
  resolveLocalApproachId,
  resolveMagicFoxApproachId,
} from '../../lib/approachIds';

function ModelCheckRow({ checked, onToggle, title, meta, badge, disabled }) {
  return (
    <label className={`platform-model-row${checked ? ' is-on' : ''}${disabled ? ' is-disabled' : ''}`}>
      <input type="checkbox" checked={checked} disabled={disabled} onChange={onToggle} />
      <span className="platform-model-main">
        <span className="platform-model-name">{title}</span>
        {meta && <span className="platform-model-meta">{meta}</span>}
      </span>
      {badge && <span className="platform-model-badge">{badge}</span>}
    </label>
  );
}

const MODEL_TABS = [
  { id: 'deploy', label: '部署模型' },
  { id: 'train', label: '训练模型' },
  { id: 'registry', label: '已注册' },
];

const DATA_SOURCE_TABS = [
  { id: 'sync', label: '已同步数据集' },
  { id: 'query', label: '查询结果' },
  { id: 'dir', label: '本地目录' },
];

export default function PlatformPredictPanel({
  project,
  projects = [],
  onProjectChange,
  datasets,
  preselectedDatasetId = null,
  preselectedTaskId = null,
  preselectedIndices = null,
  onCreated,
  onGoJobs,
  standalone = false,
  allowLocalDir = true,
  compactIntro = false,
  wideLayout = false,
}) {
  const [datasetId, setDatasetId] = useState('');
  const [dataSourceType, setDataSourceType] = useState('sync');
  const [localDir, setLocalDir] = useState('');
  const [queryTaskId, setQueryTaskId] = useState('');
  const [queryIndices, setQueryIndices] = useState(null);
  const [modelTab, setModelTab] = useState('deploy');
  const [deployModels, setDeployModels] = useState([]);
  const [trainModels, setTrainModels] = useState([]);
  const [registryModels, setRegistryModels] = useState([]);
  const [selectedDeploy, setSelectedDeploy] = useState({});
  const [selectedTrain, setSelectedTrain] = useState({});
  const [selectedRegistry, setSelectedRegistry] = useState({});
  const [datasetStatus, setDatasetStatus] = useState(null);
  const [loadingModels, setLoadingModels] = useState(false);
  const [syncingTrain, setSyncingTrain] = useState(false);
  const [trainSyncMeta, setTrainSyncMeta] = useState(null);
  const [busy, setBusy] = useState(false);
  const [threshold, setThreshold] = useState('0.1');
  const [maxSize, setMaxSize] = useState('1536');
  const [device, setDevice] = useState('');
  const [intra, setIntra] = useState(1);
  const [namePrefix, setNamePrefix] = useState('');
  const [localApproachId, setLocalApproachId] = useState(null);

  const magicFoxApproachId = resolveMagicFoxApproachId(project);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await api.getConfig();
        if (alive && res.success) {
          setLocalApproachId(resolveLocalApproachId(res.config));
        }
      } catch { /* ignore */ }
    })();
    return () => { alive = false; };
  }, []);

  const loadRegistry = useCallback(async () => {
    try {
      const rRes = await api.forgeModels(true);
      if (rRes.success) {
        const all = rRes.data || [];
        setRegistryModels(
          all.filter((m) => registryMatchesApproaches(m, localApproachId, magicFoxApproachId)),
        );
      }
    } catch { /* ignore */ }
  }, [localApproachId, magicFoxApproachId]);

  useEffect(() => {
    if (preselectedDatasetId) setDatasetId(String(preselectedDatasetId));
  }, [preselectedDatasetId]);

  useEffect(() => {
    if (preselectedTaskId) {
      setDataSourceType('query');
      setQueryTaskId(String(preselectedTaskId));
      setQueryIndices(Array.isArray(preselectedIndices) && preselectedIndices.length ? preselectedIndices : null);
    }
  }, [preselectedTaskId, preselectedIndices]);

  useEffect(() => {
    if (!datasets.length) {
      setDatasetId('');
      return;
    }
    if (!datasetId || !datasets.some((d) => String(d.id) === String(datasetId))) {
      setDatasetId(String(datasets[0].id));
    }
  }, [datasets, datasetId]);

  const loadTrainModels = useCallback(async (force = false) => {
    if (!project?.id) {
      setTrainModels([]);
      return;
    }
    setSyncingTrain(true);
    try {
      const mfQs = magicFoxApproachId ? `&approach_id=${magicFoxApproachId}` : '';
      const res = force
        ? await api.forgeSyncTrainModels(project.id, true)
        : await api.getTrainingModels(`?project_id=${project.id}${mfQs}&limit=200`);
      if (res.success) {
        setTrainModels(res.models || res.data || []);
        setTrainSyncMeta(res.meta || { count: (res.models || []).length, synced_count: res.synced_count });
      }
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setSyncingTrain(false);
    }
  }, [project?.id, magicFoxApproachId]);

  useEffect(() => {
    if (!localApproachId) {
      setDeployModels([]);
      loadRegistry();
      return;
    }
    let alive = true;
    setLoadingModels(true);
    (async () => {
      try {
        const dRes = await api.getDeployedModels(`?approach_id=${localApproachId}&limit=100`);
        if (!alive) return;
        if (dRes.success) setDeployModels(dRes.models || dRes.data || []);
        await loadRegistry();
      } catch { /* ignore */ }
      finally { if (alive) setLoadingModels(false); }
    })();
    return () => { alive = false; };
  }, [localApproachId, loadRegistry]);

  useEffect(() => {
    if (!project?.id) {
      setTrainModels([]);
      return;
    }
    loadTrainModels(false);
  }, [project?.id, magicFoxApproachId, loadTrainModels]);

  useEffect(() => {
    if (!datasetId) {
      setDatasetStatus(null);
      return;
    }
    let alive = true;
    (async () => {
      try {
        const res = await api.forgeSyncDatasetStatus(datasetId);
        if (alive && res.success) setDatasetStatus(res.data);
      } catch { /* ignore */ }
    })();
    return () => { alive = false; };
  }, [datasetId]);

  const deploySelections = useMemo(
    () => Object.keys(selectedDeploy).filter((k) => selectedDeploy[k]),
    [selectedDeploy],
  );
  const trainSelections = useMemo(
    () => Object.keys(selectedTrain).filter((k) => selectedTrain[k]),
    [selectedTrain],
  );
  const registrySelections = useMemo(
    () => Object.keys(selectedRegistry).filter((k) => selectedRegistry[k]),
    [selectedRegistry],
  );
  const totalSelected = deploySelections.length + trainSelections.length + registrySelections.length;

  const filteredRegistry = useMemo(
    () => registryModels.filter((m) => {
      if (m.source === 'modeldeploy' && selectedDeploy[m.source_ref]) return false;
      if (m.source === 'modeltrainconfig' && selectedTrain[m.source_ref]) return false;
      return true;
    }),
    [registryModels, selectedDeploy, selectedTrain],
  );

  const toggleDeploy = (id) => setSelectedDeploy((p) => ({ ...p, [id]: !p[id] }));
  const toggleTrain = (id) => setSelectedTrain((p) => ({ ...p, [id]: !p[id] }));
  const toggleRegistry = (id) => setSelectedRegistry((p) => ({ ...p, [id]: !p[id] }));

  const selectAllDeploy = (on) => {
    const next = {};
    deployModels.forEach((m) => {
      if (m.path_resolvable !== false) next[m.id] = on;
    });
    setSelectedDeploy(next);
  };

  const selectAllTrain = (on) => {
    const next = {};
    trainModels.forEach((m) => { next[m.id] = on; });
    setSelectedTrain(next);
  };

  const usingSyncDataset = dataSourceType === 'sync';
  const usingLocalDir = dataSourceType === 'dir';
  const usingQueryTask = dataSourceType === 'query';

  const submit = async () => {
    if (usingSyncDataset && !datasetId) {
      toast('请选择数据集', 'error');
      return;
    }
    if (usingLocalDir && !localDir.trim()) {
      toast('请输入本地图片目录路径', 'error');
      return;
    }
    if (usingQueryTask && !queryTaskId.trim()) {
      toast('请输入查询 task_id', 'error');
      return;
    }
    if (!totalSelected) {
      toast('请至少选择一个模型', 'error');
      return;
    }
    if (threshold === '' || Number.isNaN(Number(threshold))) {
      toast('请填写置信度阈值', 'error');
      return;
    }
    if (deploySelections.length && !localApproachId) {
      toast('部署模型需要在 设置 → 检测项目 配置本地总控 Approach（defect_approach_id）', 'error');
      return;
    }
    if (trainSelections.length && !project?.id) {
      toast('训练模型需要关联 Magic-Fox 项目', 'error');
      return;
    }
    if (trainSelections.length && !magicFoxApproachId) {
      toast('所选 Magic-Fox 项目未配置 Approach ID，请在训练平台编辑项目', 'error');
      return;
    }
    if (usingSyncDataset && !datasetStatus?.local_count) {
      toast('该数据集本地尚无图片，请先同步', 'error');
      return;
    }
    const ds = datasets.find((d) => String(d.id) === String(datasetId));
    setBusy(true);
    try {
      const body = {
        platform_project_id: project?.id,
        name_prefix: namePrefix.trim() || (usingSyncDataset
          ? (ds?.name || 'predict')
          : usingQueryTask
            ? `query-${queryTaskId.trim().slice(0, 8)}`
            : (localDir.trim().split('/').filter(Boolean).pop() || 'predict')),
        deploy_model_ids: deploySelections.map(Number),
        train_model_ids: trainSelections.map(Number),
        model_ids: registrySelections.map(Number),
        intra_concurrency: Number(intra) || 1,
      };
      if (usingSyncDataset) {
        body.sync_dataset_id = Number(datasetId);
      } else if (usingQueryTask) {
        body.image_source = {
          type: 'task',
          task_id: queryTaskId.trim(),
        };
        if (queryIndices?.length) {
          body.image_source.selected_indices = queryIndices;
        }
      } else {
        body.image_source = { type: 'dir', path: localDir.trim() };
      }
      if (threshold !== '') body.threshold = Number(threshold);
      if (maxSize !== '') body.max_size = Number(maxSize);
      if (device) body.device = device.trim();
      const res = await api.forgeEnqueuePredictBatch(body);
      if (res.success) {
        const ids = (res.jobs || []).map((j) => `#${j.job_id}`).join('、');
        showResultModal(
          `已创建 ${res.model_count} 个预测任务（${res.total_images} 张/任务）${ids ? `\n${ids}` : ''}`,
          { title: '预测任务已提交' },
        );
        onCreated?.(res);
      }
    } catch (e) {
      showErrorModal(e.message, { title: '创建预测任务失败' });
    } finally {
      setBusy(false);
    }
  };

  if (!project && !standalone) return null;

  const selectedDs = datasets.find((d) => String(d.id) === String(datasetId));
  const canSubmit = totalSelected > 0 && (
    (usingSyncDataset && datasetStatus?.local_count)
    || (usingLocalDir && localDir.trim())
    || (usingQueryTask && queryTaskId.trim())
  );

  return (
    <div className={`platform-predict-panel${wideLayout ? ' platform-predict-panel-wide' : ''}`} id="platform-predict">
      {!compactIntro && (
        <div className="platform-predict-intro">
          <p>
            选择数据集与模型来源发起批量预测：训练模型走 Magic-Fox 线上 API；部署/已注册模型在本地加载权重。
            每个模型独立一个后台作业，进度见 <Link to="/jobs">预测任务</Link> 页
            {onGoJobs ? <>，同步进度见 <button type="button" className="platform-inline-link" onClick={onGoJobs}>同步任务</button> 工作区</> : '。'}
          </p>
        </div>
      )}

      {standalone && projects.length > 0 && (
        <section className="platform-step platform-surface-card">
          <div className="platform-step-head">
            <span className="platform-step-num">0</span>
            <div>
              <h4>关联项目</h4>
              <p className="muted">部署模型按设置中的本地总控 Approach；训练模型按 Magic-Fox 项目</p>
            </div>
          </div>
          <div className="forge-form-grid platform-predict-form">
            <label className="forge-span2">
              Magic-Fox 项目
              <select
                value={project?.id ?? ''}
                onChange={(e) => onProjectChange?.(e.target.value ? Number(e.target.value) : null)}
              >
                <option value="">不关联项目（仅已注册模型）</option>
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}{p.approach_id ? ` · MF approach ${p.approach_id}` : ' · 未配置 MF Approach'}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </section>
      )}

      {deploySelections.length > 0 && !localApproachId && (
        <div className="platform-surface-card platform-predict-alert">
          <p>
            部署模型需要在 <Link to="/config">设置 → 检测项目</Link> 配置
            <code> defect_approach_id</code>（本地总控 Approach），或改用「已注册」Tab。
          </p>
        </div>
      )}

      {trainSelections.length > 0 && project && !magicFoxApproachId && (
        <div className="platform-surface-card platform-predict-alert">
          <p>
            训练模型需要 Magic-Fox 项目的 Approach ID。
            请在 <Link to="/training">训练平台</Link> 编辑项目补充，或改用「已注册」Tab。
          </p>
        </div>
      )}

      {trainSelections.length > 0 && !project && standalone && (
        <div className="platform-surface-card platform-predict-alert">
          <p>使用训练模型请先在上方的「关联项目」中选择一个 Magic-Fox 项目。</p>
        </div>
      )}

      {!project && standalone && totalSelected > 0 && trainSelections.length === 0 && deploySelections.length === 0 && (
        <div className="platform-surface-card platform-predict-alert platform-predict-alert-info">
          <p>仅使用「已注册」或「部署模型」时可不关联 Magic-Fox 项目；训练模型需选择项目。</p>
        </div>
      )}

      <div className="platform-predict-steps">
        <section className="platform-step platform-surface-card">
          <div className="platform-step-head">
            <span className="platform-step-num">1</span>
            <div>
              <h4>选择数据集</h4>
              <p className="muted">已同步数据集或本地图片目录</p>
            </div>
          </div>

          {allowLocalDir && (
            <div className="platform-model-tabs platform-data-source-tabs">
              {DATA_SOURCE_TABS.filter((t) => t.id !== 'dir' || allowLocalDir).map((t) => (
                <button
                  key={t.id}
                  type="button"
                  className={`platform-model-tab${dataSourceType === t.id ? ' is-active' : ''}`}
                  onClick={() => setDataSourceType(t.id)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          )}

          {usingSyncDataset && (
            <>
              <div className="forge-form-grid platform-predict-form">
                <label className="forge-span2">
                  数据集
                  <select value={datasetId} onChange={(e) => setDatasetId(e.target.value)} disabled={!datasets.length}>
                    {!datasets.length && <option value="">暂无数据集 — 请先在训练平台添加</option>}
                    {datasets.map((d) => (
                      <option key={d.id} value={d.id}>{d.name}（{d.source_type === 'snapshot' ? '快照' : '底库'} #{d.source_id}）</option>
                    ))}
                  </select>
                </label>
                <label>
                  本地图片
                  <input readOnly className={datasetStatus?.local_count ? 'platform-input-ok' : ''} value={datasetStatus ? `${datasetStatus.local_count} 张` : '…'} />
                </label>
              </div>
              {selectedDs && !datasetStatus?.local_count && (
                <p className="platform-step-hint hint">
                  该数据集本地尚无图片，请先在 <Link to="/training">训练平台</Link> 同步，或改用「本地目录」直接指定路径。
                </p>
              )}
              {!datasets.length && standalone && (
                <p className="platform-step-hint hint">
                  还没有同步数据集？前往 <Link to="/training">训练平台</Link> 发现导入并同步，或切换到「本地目录」。
                </p>
              )}
            </>
          )}

          {usingQueryTask && (
            <div className="forge-form-grid platform-predict-form">
              <label className="forge-span2">
                查询 task_id
                <input
                  value={queryTaskId}
                  onChange={(e) => setQueryTaskId(e.target.value)}
                  placeholder="查询页执行后自动填入，或手动粘贴"
                  spellCheck={false}
                />
              </label>
              <label>
                图片范围
                <input
                  readOnly
                  className={queryIndices?.length ? 'platform-input-ok' : ''}
                  value={queryIndices?.length ? `已选 ${queryIndices.length} 条` : '全部结果'}
                />
              </label>
              <p className="platform-step-hint hint forge-span2">
                在 <Link to="/">查询页</Link> 执行筛选后，点击结果栏「预测」可自动带入 task_id；若勾选了部分图片则只预测选中项。
              </p>
            </div>
          )}

          {usingLocalDir && (
            <div className="forge-form-grid platform-predict-form">
              <label className="forge-span2">
                图片目录
                <input
                  value={localDir}
                  onChange={(e) => setLocalDir(e.target.value)}
                  placeholder="服务器上的绝对路径，如 /data/images/batch_01"
                  spellCheck={false}
                />
              </label>
              <p className="platform-step-hint hint forge-span2">
                目录需在服务器可访问路径内；支持 jpg/png/bmp 等常见格式，子目录会递归扫描。
              </p>
            </div>
          )}
        </section>

        <section className="platform-step platform-surface-card">
          <div className="platform-step-head">
            <span className="platform-step-num">2</span>
            <div>
              <h4>预测参数</h4>
              <p className="muted">提交时将写入作业配置；部署/已注册模型走本地推理，训练模型走线上 API</p>
            </div>
          </div>
          <div className="forge-form-grid platform-predict-form">
            <label>
              置信度阈值 *
              <input
                type="number"
                step="0.01"
                min={0}
                max={1}
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                placeholder="0.1"
              />
            </label>
            <label>
              输入尺寸 image_size
              <input
                type="number"
                min={256}
                step={64}
                value={maxSize}
                onChange={(e) => setMaxSize(e.target.value)}
                placeholder="1536"
                title="对应 max_size，本地模型推理时的最长边"
              />
            </label>
            <label>
              推理设备
              <input
                value={device}
                onChange={(e) => setDevice(e.target.value)}
                placeholder="cuda:0 / cpu（本地模型）"
              />
            </label>
            <label>
              任务内并发
              <input
                type="number"
                min={1}
                value={intra}
                onChange={(e) => setIntra(e.target.value)}
                title="单作业内多图并行，共享一次模型加载"
              />
            </label>
            <label className="forge-span2">
              作业名称前缀
              <input
                value={namePrefix}
                onChange={(e) => setNamePrefix(e.target.value)}
                placeholder="留空则按数据集/目录名自动生成"
              />
            </label>
          </div>
        </section>

        <section className="platform-step platform-surface-card">
          <div className="platform-step-head">
            <span className="platform-step-num">3</span>
            <div className="platform-step-head-main">
              <div>
                <h4>选择模型</h4>
                <p className="muted">可多选，每个模型创建一个独立预测作业</p>
              </div>
              {totalSelected > 0 && (
                <span className="platform-pill platform-pill-ok">已选 {totalSelected} 个</span>
              )}
            </div>
          </div>

          <div className="platform-model-tabs">
            {MODEL_TABS.map((t) => {
              const count = t.id === 'deploy' ? deployModels.length
                : t.id === 'train' ? trainModels.length
                  : filteredRegistry.length;
              const selected = t.id === 'deploy' ? deploySelections.length
                : t.id === 'train' ? trainSelections.length
                  : registrySelections.length;
              return (
                <button
                  key={t.id}
                  type="button"
                  className={`platform-model-tab${modelTab === t.id ? ' is-active' : ''}`}
                  onClick={() => setModelTab(t.id)}
                >
                  {t.label}
                  {count > 0 && <span className="platform-model-tab-count">{selected || count}</span>}
                </button>
              );
            })}
          </div>

          {modelTab === 'deploy' && (
            <div className="platform-model-pane">
              <div className="platform-model-section-head">
                <span className="muted">
                  {deployModels.length
                    ? `${deployModels.length} 个部署模型（本地总控 Approach ${localApproachId}）`
                    : localApproachId
                      ? '暂无部署模型'
                      : '未配置本地总控 Approach'}
                </span>
                {!!deployModels.length && (
                  <span className="platform-model-actions">
                    <button type="button" className="btn sm btn-ghost" onClick={() => selectAllDeploy(true)}>全选</button>
                    <button type="button" className="btn sm btn-ghost" onClick={() => selectAllDeploy(false)}>清空</button>
                  </span>
                )}
              </div>
              {loadingModels && <p className="muted platform-model-empty">加载模型列表…</p>}
              {!loadingModels && !deployModels.length && (
                <p className="muted platform-model-empty">
                  {localApproachId
                    ? `本地总控 Approach ${localApproachId} 下暂无可用部署模型`
                    : '请先在 设置 → 检测项目 配置 defect_approach_id'}
                </p>
              )}
              <div className="platform-model-list">
                {deployModels.map((m) => {
                  const disabled = m.path_resolvable === false;
                  return (
                    <ModelCheckRow
                      key={`deploy-${m.id}`}
                      checked={!!selectedDeploy[m.id]}
                      disabled={disabled}
                      onToggle={() => toggleDeploy(m.id)}
                      title={m.deploy_name || `模型 #${m.id}`}
                      meta={[m.model_type, m.c_time?.slice(0, 10)].filter(Boolean).join(' · ')}
                      badge={disabled ? '路径不可用' : '本地预测'}
                    />
                  );
                })}
              </div>
            </div>
          )}

          {modelTab === 'train' && (
            <div className="platform-model-pane">
              <div className="platform-model-section-head">
                <span className="muted">
                  {trainModels.length
                    ? `${trainModels.length} 个训练模型（Magic-Fox${magicFoxApproachId ? ` · approach ${magicFoxApproachId}` : ''}）`
                    : project?.id
                      ? '暂无训练模型'
                      : '请先关联 Magic-Fox 项目'}
                  {trainSyncMeta?.synced_count != null && !syncingTrain && (
                    <> · 已同步 {trainSyncMeta.synced_count} 个</>
                  )}
                </span>
                <span className="platform-model-actions">
                  {!!trainModels.length && (
                    <>
                      <button type="button" className="btn sm btn-ghost" onClick={() => selectAllTrain(true)}>全选</button>
                      <button type="button" className="btn sm btn-ghost" onClick={() => selectAllTrain(false)}>清空</button>
                    </>
                  )}
                  <button
                    type="button"
                    className="btn sm primary"
                    disabled={syncingTrain || !project?.id}
                    onClick={() => loadTrainModels(true)}
                  >
                    {syncingTrain ? '同步中…' : '从平台同步'}
                  </button>
                </span>
              </div>
              {syncingTrain && !trainModels.length && (
                <p className="muted platform-model-empty">正在从 Magic-Fox 训练页抓取模型列表…</p>
              )}
              {!syncingTrain && !loadingModels && !trainModels.length && (
                <p className="muted platform-model-empty">
                  本地库无该项目训练记录。点击「从平台同步」从 Magic-Fox 训练页拉取（需已配置认证）。
                </p>
              )}
              <div className="platform-model-list">
                {trainModels.map((m) => (
                  <ModelCheckRow
                    key={`train-${m.id}`}
                    checked={!!selectedTrain[m.id]}
                    onToggle={() => toggleTrain(m.id)}
                    title={m.model_name || `训练 #${m.id}`}
                    meta={[`train_id ${m.id}`, m.model_type, m.c_time?.slice(0, 10)].filter(Boolean).join(' · ')}
                    badge="线上 API"
                  />
                ))}
              </div>
            </div>
          )}

          {modelTab === 'registry' && (
            <div className="platform-model-pane">
              <div className="platform-model-section-head">
                <span className="muted">本地注册表中的模型（本地加载权重）</span>
              </div>
              {!filteredRegistry.length && (
                <p className="muted platform-model-empty">暂无额外可注册的模型</p>
              )}
              <div className="platform-model-list">
                {filteredRegistry.map((m) => (
                  <ModelCheckRow
                    key={`reg-${m.id}`}
                    checked={!!selectedRegistry[m.id]}
                    onToggle={() => toggleRegistry(m.id)}
                    title={m.name}
                    meta={[m.framework, m.sub_type].filter(Boolean).join('/')}
                    badge={m.source === 'modeldeploy' ? '已导入部署' : m.source === 'modeltrainconfig' ? '已导入训练' : m.source || 'manual'}
                  />
                ))}
              </div>
            </div>
          )}
        </section>
      </div>

      <div className="platform-predict-footer">
        <div className="platform-predict-footer-summary">
          {usingSyncDataset && selectedDs ? (
            <span>目标：<strong>{selectedDs.name}</strong></span>
          ) : usingQueryTask && queryTaskId.trim() ? (
            <span>目标：<strong>查询 {queryTaskId.trim().slice(0, 8)}…</strong>{queryIndices?.length ? `（${queryIndices.length} 条）` : ''}</span>
          ) : usingLocalDir && localDir.trim() ? (
            <span>目标：<strong>{localDir.trim().split('/').filter(Boolean).pop()}</strong></span>
          ) : (
            <span className="muted">请选择数据集或目录</span>
          )}
          <span className="platform-context-dot">·</span>
          <span>{totalSelected} 个模型</span>
          {trainSelections.length > 0 && (
            <>
              <span className="platform-context-dot">·</span>
              <span>阈值 {threshold || '0.1'}</span>
            </>
          )}
          {(deploySelections.length + registrySelections.length) > 0 && (
            <>
              <span className="platform-context-dot">·</span>
              <span>size {maxSize || '1536'}{device ? ` · ${device}` : ''}</span>
            </>
          )}
          {trainSelections.length > 0 && (
            <>
              <span className="platform-context-dot">·</span>
              <span>{trainSelections.length} 个走线上 API</span>
            </>
          )}
          {usingSyncDataset && datasetStatus?.local_count != null && (
            <>
              <span className="platform-context-dot">·</span>
              <span>{datasetStatus.local_count} 张图片/任务</span>
            </>
          )}
        </div>
        <button
          type="button"
          className="btn primary"
          disabled={busy || !canSubmit}
          onClick={submit}
          data-testid="predict-submit"
        >
          {busy ? '创建中…' : `创建预测任务（${totalSelected} 个模型）`}
        </button>
      </div>
    </div>
  );
}
