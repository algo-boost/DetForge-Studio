import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import UnifyToolHost from '../components/UnifyToolHost';
import PlatformPredictPanel from '../components/forge/PlatformPredictPanel';
import SceneHubNav from '../components/SceneHubNav';

function PredictTipsStrip() {
  return (
    <div className="predict-workbench-tips-strip">
      <div className="platform-surface-card predict-workbench-tip">
        <h4>数据来源</h4>
        <ul>
          <li><strong>查询结果</strong> — 在 <Link to="/">查询页</Link> 执行后点「预测」</li>
          <li><strong>已同步数据集</strong> — 在 <Link to="/training">训练平台</Link> 从 Magic-Fox 同步</li>
          <li><strong>本地目录</strong> — 直接指定服务器上的图片文件夹</li>
        </ul>
      </div>
      <div className="platform-surface-card predict-workbench-tip">
        <h4>模型来源</h4>
        <ul>
          <li><strong>部署模型</strong> — 平台 modeldeploy 表，本地加载权重</li>
          <li><strong>训练模型</strong> — Magic-Fox 线上 validation API</li>
          <li><strong>已注册</strong> — <Link to="/models">模型页</Link> 手动登记或导入的本地权重</li>
        </ul>
      </div>
      <div className="platform-surface-card predict-workbench-tip">
        <h4>预测之后</h4>
        <p className="muted">结果写入 predict_result 表，可在 <Link to="/jobs">预测任务</Link> 查看进度，在 <Link to="/">查询页</Link> 二次筛选（默认即预测结果表）。</p>
      </div>
    </div>
  );
}

export default function OnlinePredictPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const tab = params.get('tab') === 'quick' ? 'quick' : 'batch';
  const initialProjectId = params.get('project') ? Number(params.get('project')) : null;
  const initialDatasetId = params.get('dataset') ? Number(params.get('dataset')) : null;
  const initialTaskId = params.get('task') || '';
  const initialIndices = useMemo(() => {
    const raw = params.get('indices');
    if (!raw) return null;
    const nums = raw.split(',').map((s) => Number(s.trim())).filter((n) => Number.isFinite(n));
    return nums.length ? nums : null;
  }, [params]);

  const [projects, setProjects] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedProjectId, setSelectedProjectId] = useState(initialProjectId);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [pRes, dRes] = await Promise.all([
        api.forgeSyncProjects(),
        api.forgeSyncDatasets(selectedProjectId ? `?project_id=${selectedProjectId}` : ''),
      ]);
      if (pRes.success) setProjects(pRes.data || []);
      if (dRes.success) setDatasets(dRes.data || []);
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setLoading(false);
    }
  }, [selectedProjectId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!projects.length) return;
    if (initialProjectId && projects.some((p) => p.id === initialProjectId)) {
      if (selectedProjectId !== initialProjectId) setSelectedProjectId(initialProjectId);
      return;
    }
    if (selectedProjectId != null && projects.some((p) => p.id === selectedProjectId)) {
      return;
    }
    const preferred = (initialTaskId ? projects.find((p) => p.approach_id) : null)
      || projects.find((p) => p.approach_id)
      || projects[0];
    setSelectedProjectId(preferred?.id ?? null);
  }, [projects, selectedProjectId, initialProjectId, initialTaskId]);

  const project = useMemo(
    () => projects.find((p) => p.id === selectedProjectId) || null,
    [projects, selectedProjectId],
  );

  const setTab = (next) => {
    const nextParams = new URLSearchParams(params);
    if (next === 'quick') nextParams.set('tab', 'quick');
    else nextParams.delete('tab');
    setParams(nextParams, { replace: true });
  };

  const handleProjectChange = (pid) => {
    setSelectedProjectId(pid);
    const nextParams = new URLSearchParams(params);
    if (pid) nextParams.set('project', String(pid));
    else nextParams.delete('project');
    nextParams.delete('dataset');
    setParams(nextParams, { replace: true });
  };

  const handleCreated = () => {
    navigate('/jobs');
  };

  return (
    <div className="panel active predict-workbench-page">
      <SceneHubNav variant="predict" />

      <header className="predict-workbench-header">
        <div className="predict-workbench-title">
          <h2>在线预测</h2>
          <p className="muted">选择数据来源与模型，设定阈值 / image_size 等参数后提交后台预测任务</p>
        </div>
        <div className="predict-workbench-tabs">
          <button
            type="button"
            className={`predict-workbench-tab${tab === 'batch' ? ' is-active' : ''}`}
            onClick={() => setTab('batch')}
          >
            批量预测
          </button>
          <button
            type="button"
            className={`predict-workbench-tab${tab === 'quick' ? ' is-active' : ''}`}
            onClick={() => setTab('quick')}
          >
            临时上传对比
          </button>
        </div>
      </header>

      {tab === 'batch' && (
        <>
          <PredictTipsStrip />
          <div className="predict-workbench-body predict-workbench-body-wide">
            {loading && !projects.length ? (
              <div className="platform-surface-card predict-workbench-loading">
                <p className="muted">加载项目与数据集…</p>
              </div>
            ) : (
              <PlatformPredictPanel
                standalone
                wideLayout
                compactIntro
                allowLocalDir
                project={project}
                projects={projects}
                onProjectChange={handleProjectChange}
                datasets={datasets}
                preselectedDatasetId={initialDatasetId}
                preselectedTaskId={initialTaskId}
                preselectedIndices={initialIndices}
                onCreated={handleCreated}
              />
            )}
          </div>
        </>
      )}

      {tab === 'quick' && (
        <div className="predict-workbench-quick">
          <p className="predict-workbench-quick-intro muted">
            快速上传模型与图片做即时对比（DetUnify），结果不落库。批量评测请用「批量预测」Tab。
          </p>
          <UnifyToolHost />
        </div>
      )}
    </div>
  );
}
