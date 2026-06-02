import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import JobsList from '../components/forge/JobsList';
import SceneHubNav from '../components/SceneHubNav';
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

export default function JobsPage() {
  const [jobs, setJobs] = useState([]);
  const [schema, setSchema] = useState({ ready: true, database: 'detforge' });
  const [detailId, setDetailId] = useState(null);
  const [jobOffset, setJobOffset] = useState(0);
  const [jobTotal, setJobTotal] = useState(0);
  const timer = useRef(null);
  const jobsRef = useRef([]);

  const load = async (off = jobOffset) => {
    try {
      const j = await api.forgeJobs(`?job_type=predict&limit=${JOBS_PAGE}&offset=${off}`);
      if (j.success) {
        setJobs(j.data || []);
        jobsRef.current = j.data || [];
        setJobTotal(j.total || 0);
        setJobOffset(off);
      }
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

  return (
    <div className="panel active pjobs-page">
      <SceneHubNav variant="predict" />
      <header className="pjobs-header">
        <div>
          <div className="topbar-title">预测任务</div>
          <p className="pjobs-header-desc">
            查看后台预测作业进度、日志与结果（写库 <code>{schema.database}</code>）·
            新建任务请前往 <Link to="/online-predict">在线预测</Link>
          </p>
        </div>
        <div className="pjobs-header-actions">
          <Link to="/online-predict" className="btn btn-sm btn-primary">发起批量预测</Link>
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
        </div>
      </header>

      {!schema.ready && (
        <div className="pjobs-schema-banner">
          <span>写库 <code>{schema.database}</code> 尚未初始化，预测结果无法写入。</span>
          <button type="button" className="btn btn-sm btn-primary" onClick={initSchema}>立即建库建表</button>
        </div>
      )}

      <div className="pjobs-workspace">
        <SurfaceCard
          title="预测作业列表"
          desc="支持暂停 / 继续 / 重试；详情中可查看运行日志与预测结果"
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
            emptyText="暂无预测作业。请前往「在线预测」选择数据集与模型并设定参数后提交。"
          />
        </SurfaceCard>
      </div>
    </div>
  );
}
