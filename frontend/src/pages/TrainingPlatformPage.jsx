import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import SyncJobsPanel from '../components/forge/SyncJobsPanel';
import PlatformPredictPanel from '../components/forge/PlatformPredictPanel';
import ProjectSidebar from '../components/forge/training/ProjectSidebar';
import PlatformOverview from '../components/forge/training/PlatformOverview';
import DiscoverPanel from '../components/forge/training/DiscoverPanel';
import DatasetSection, { ProjectForm } from '../components/forge/training/DatasetSection';
import DatasetTracePanel from '../components/forge/training/DatasetTracePanel';
import PlatformTabBar from '../components/forge/training/PlatformTabBar';
import WorkspaceContextBar from '../components/forge/training/WorkspaceContextBar';
import { PLATFORM_TABS, tabFromHash } from '../components/forge/training/platformUtils';

function AuthPill({ authOk, authConfigured }) {
  if (authOk === true) return <span className="platform-pill platform-pill-ok">已连接</span>;
  if (authOk === false) return <span className="platform-pill platform-pill-err">认证失败</span>;
  if (!authConfigured) return <span className="platform-pill platform-pill-warn">未配置</span>;
  return <span className="platform-pill">待验证</span>;
}

function OnboardingEmpty({ onNewProject, onImported, authConfigured, authOk }) {
  return (
    <div className="platform-onboarding">
      <div className="platform-onboarding-hero">
        <div className="platform-onboarding-card">
          <div className="platform-onboarding-badge">Magic-Fox 训练平台</div>
          <h3>连接平台，同步数据，批量预测</h3>
          <p>在本地管理 Magic-Fox 项目与数据集，一键同步 COCO 标注，并对多模型发起预测任务。</p>
          <ol className="platform-onboarding-steps">
            <li className={authConfigured || authOk ? 'is-done' : ''}>
              {authConfigured || authOk ? '平台认证已配置' : <>在 <Link to="/config">设置</Link> 配置 Magic-Fox 认证</>}
            </li>
            <li>新建项目，或从 URL 发现导入</li>
            <li>同步数据集 → 创建预测任务</li>
          </ol>
          <button type="button" className="btn primary" onClick={onNewProject}>新建第一个项目</button>
        </div>
        <div className="platform-onboarding-aside">
          <div className="platform-onboarding-feature">
            <div className="platform-onboarding-feature-icon">01</div>
            <div>
              <strong>发现导入</strong>
              <p>粘贴 Magic-Fox 页面 URL，自动解析底库与快照</p>
            </div>
          </div>
          <div className="platform-onboarding-feature">
            <div className="platform-onboarding-feature-icon">02</div>
            <div>
              <strong>增量同步</strong>
              <p>拉取图片与 COCO 到本地，支持写库与样本图库</p>
            </div>
          </div>
          <div className="platform-onboarding-feature">
            <div className="platform-onboarding-feature-icon">03</div>
            <div>
              <strong>多模型预测</strong>
              <p>部署/训练模型多选，一模型一作业并行执行</p>
            </div>
          </div>
        </div>
      </div>
      <DiscoverPanel projects={[]} selectedProject={null} onImported={onImported} />
    </div>
  );
}

export default function TrainingPlatformPage() {
  const [projects, setProjects] = useState([]);
  const [datasets, setDatasets] = useState([]);
  const [selectedProject, setSelectedProject] = useState(null);
  const [activeTab, setActiveTab] = useState(() => tabFromHash() || 'overview');
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [authOk, setAuthOk] = useState(null);
  const [authConfigured, setAuthConfigured] = useState(false);
  const [syncJobsKey, setSyncJobsKey] = useState(0);
  const [predictDatasetId, setPredictDatasetId] = useState(null);
  const [syncingAll, setSyncingAll] = useState(false);

  const load = useCallback(async () => {
    try {
      const [pRes, dRes, cfgRes] = await Promise.all([
        api.forgeSyncProjects(),
        api.forgeSyncDatasets(selectedProject ? `?project_id=${selectedProject}` : ''),
        api.getConfig(),
      ]);
      if (pRes.success) setProjects(pRes.data || []);
      if (dRes.success) setDatasets(dRes.data || []);
      if (cfgRes.success) {
        setAuthConfigured(!!cfgRes.config?.magic_fox_configured);
        if (cfgRes.config?.magic_fox_configured) setAuthOk(true);
      }
    } catch (e) { toast(e.message, 'error'); }
  }, [selectedProject]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (projects.length && (selectedProject == null || !projects.some((p) => p.id === selectedProject))) {
      setSelectedProject(projects[0].id);
    }
  }, [projects, selectedProject]);

  const currentProject = useMemo(
    () => projects.find((p) => p.id === selectedProject) || null,
    [projects, selectedProject],
  );

  const navigateTab = useCallback((tab) => {
    setActiveTab(tab);
    window.location.hash = tab;
    try {
      if (selectedProject) sessionStorage.setItem(`platform-tab-${selectedProject}`, tab);
    } catch { /* ignore */ }
  }, [selectedProject]);

  useEffect(() => {
    if (!selectedProject) return;
    try {
      const saved = sessionStorage.getItem(`platform-tab-${selectedProject}`);
      if (saved && PLATFORM_TABS.some((t) => t.id === saved) && !tabFromHash()) {
        setActiveTab(saved);
      }
    } catch { /* ignore */ }
  }, [selectedProject]);

  useEffect(() => {
    const onHash = () => {
      const t = tabFromHash();
      if (t) setActiveTab(t);
    };
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  const testAuth = async () => {
    try {
      const res = await api.forgeSyncTestAuth();
      setAuthOk(!!res.connected);
      toast(res.connected ? 'Magic-Fox 认证正常' : '认证异常', res.connected ? 'success' : 'error');
    } catch (e) {
      setAuthOk(false);
      toast(e.message, 'error');
    }
  };

  const deleteProject = async (id) => {
    if (!window.confirm(
      '删除项目及其下所有数据集同步配置？\n\n'
      + '仅移除本工具中的配置，不影响 Magic-Fox 远程数据集，也不会删除本地已下载文件。',
    )) return;
    try {
      await api.forgeSyncDeleteProject(id);
      toast('项目已删除');
      if (selectedProject === id) setSelectedProject(null);
      load();
    } catch (e) { toast(e.message, 'error'); }
  };

  const handleImported = (projectId) => {
    if (projectId) setSelectedProject(projectId);
    setSyncJobsKey((k) => k + 1);
    load();
    navigateTab('datasets');
  };

  const bumpSyncJobs = () => setSyncJobsKey((k) => k + 1);

  const openPredictForDataset = (id) => {
    setPredictDatasetId(id);
    navigateTab('predict');
  };

  const syncAllFromOverview = async () => {
    if (!datasets.length) return;
    setSyncingAll(true);
    try {
      let n = 0;
      for (const ds of datasets) {
        const res = await api.forgeSyncRun(ds.id, { async: true });
        if (res.success) n += 1;
      }
      toast(`已提交 ${n} 个同步任务`);
      bumpSyncJobs();
      load();
      navigateTab('jobs');
    } catch (e) { toast(e.message, 'error'); }
    finally { setSyncingAll(false); }
  };

  const openNewProject = () => {
    setEditingProject(null);
    setShowProjectForm(true);
    if (!currentProject) navigateTab('overview');
  };

  const openEditProject = (p) => {
    setEditingProject(p);
    setShowProjectForm(true);
  };

  const tabCounts = useMemo(() => ({
    datasets: datasets.length,
  }), [datasets.length]);

  return (
    <div className="panel active training-platform-page">
      <div className="platform-page-header">
        <div>
          <div className="platform-page-header-row">
            <h2>训练平台</h2>
            <AuthPill authOk={authOk} authConfigured={authConfigured} />
          </div>
          <p className="panel-desc">Magic-Fox 项目 · 数据集同步 · 多模型预测</p>
        </div>
        <div className="platform-page-header-actions">
          <Link className="btn sm btn-ghost" to="/jobs">预测任务 ↗</Link>
          <Link className="btn sm btn-ghost" to="/models">模型注册 ↗</Link>
          <button type="button" className="btn sm btn-ghost" onClick={testAuth}>验证认证</button>
          <button type="button" className="btn sm btn-ghost" onClick={load}>刷新</button>
        </div>
      </div>

      {!projects.length && showProjectForm && (
        <div className="platform-onboarding-form">
          <ProjectForm
            project={editingProject}
            onSaved={() => { setShowProjectForm(false); setEditingProject(null); load(); }}
            onCancel={() => { setShowProjectForm(false); setEditingProject(null); }}
          />
        </div>
      )}

      {!projects.length && !showProjectForm && (
        <OnboardingEmpty
          onNewProject={openNewProject}
          onImported={(pid) => {
            if (pid) setSelectedProject(pid);
            setSyncJobsKey((k) => k + 1);
            load();
            navigateTab('datasets');
          }}
          authConfigured={authConfigured}
          authOk={authOk}
        />
      )}

      {!!projects.length && (
        <div className="platform-layout">
          <ProjectSidebar
            projects={projects}
            selectedProject={selectedProject}
            currentProject={currentProject}
            onSelectProject={setSelectedProject}
            onDeleteProject={deleteProject}
            onNewProject={openNewProject}
            onEditProject={openEditProject}
          />

          <main className="platform-main">
            {currentProject && (
              <>
                <WorkspaceContextBar
                  project={currentProject}
                  datasetCount={datasets.length}
                  authOk={authOk}
                  authConfigured={authConfigured}
                  onTestAuth={testAuth}
                />
                <PlatformTabBar
                  activeTab={activeTab}
                  onTabChange={navigateTab}
                  counts={tabCounts}
                />
              </>
            )}

            {(showProjectForm || editingProject) && (
              <ProjectForm
                project={editingProject}
                onSaved={() => { setShowProjectForm(false); setEditingProject(null); load(); }}
                onCancel={() => { setShowProjectForm(false); setEditingProject(null); }}
              />
            )}

            {currentProject && (
              <div className="platform-workspace">
                {activeTab === 'overview' && (
                  <PlatformOverview
                    project={currentProject}
                    datasets={datasets}
                    onNavigate={navigateTab}
                    onSyncAll={syncAllFromOverview}
                    syncingAll={syncingAll}
                  />
                )}

                {activeTab === 'discover' && (
                  <DiscoverPanel
                    projects={projects}
                    selectedProject={selectedProject}
                    onImported={handleImported}
                  />
                )}

                {activeTab === 'datasets' && (
                  <DatasetSection
                    project={currentProject}
                    projectId={selectedProject}
                    datasets={datasets}
                    onRefresh={load}
                    onSyncStarted={bumpSyncJobs}
                    onPredict={openPredictForDataset}
                    onGoJobs={() => navigateTab('jobs')}
                    onGoDiscover={() => navigateTab('discover')}
                    onGoTrace={() => navigateTab('trace')}
                  />
                )}

                {activeTab === 'trace' && (
                  <DatasetTracePanel
                    datasets={datasets}
                    projectId={selectedProject}
                  />
                )}

                {activeTab === 'predict' && (
                  <PlatformPredictPanel
                    project={currentProject}
                    datasets={datasets}
                    preselectedDatasetId={predictDatasetId}
                    onGoJobs={() => navigateTab('jobs')}
                  />
                )}

                {activeTab === 'jobs' && (
                  <div className="platform-jobs-tab">
                    <SyncJobsPanel refreshKey={syncJobsKey} embedded />
                    <div className="platform-surface-card platform-jobs-hint">
                      <p>模型<strong>预测</strong>作业在侧栏 <Link to="/jobs">预测任务</Link> 页管理；查询页可将数据源切换为「预测结果表」做二次筛选。</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
