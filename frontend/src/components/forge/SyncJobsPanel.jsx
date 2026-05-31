import { useEffect, useRef, useState } from 'react';
import { api, toast } from '../../api/client';
import { STATUS_LABEL } from './JobWidgets';
import JobsList from './JobsList';

const PAGE_SIZE = 50;

export default function SyncJobsPanel({ refreshKey = 0, embedded = false }) {
  const [jobs, setJobs] = useState([]);
  const [jobTotal, setJobTotal] = useState(0);
  const [jobOffset, setJobOffset] = useState(0);
  const [detailId, setDetailId] = useState(null);
  const timer = useRef(null);
  const jobsRef = useRef([]);

  const load = async (off = jobOffset) => {
    try {
      const j = await api.forgeJobs(`?job_type=dataset_sync&limit=${PAGE_SIZE}&offset=${off}`);
      if (j.success) {
        setJobs(j.data || []);
        jobsRef.current = j.data || [];
        setJobTotal(j.total || 0);
        setJobOffset(off);
      }
    } catch { /* 静默轮询失败 */ }
  };

  const scheduleNext = () => {
    const active = jobsRef.current.some((j) => j.status === 'running' || j.status === 'pending');
    timer.current = setTimeout(async () => { await load(jobOffset); scheduleNext(); }, active ? 3000 : 12000);
  };

  useEffect(() => {
    load(0).then(scheduleNext);
    return () => clearTimeout(timer.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [refreshKey]);

  const control = async (id, action) => {
    try {
      const r = await api.forgeControlJob(id, action);
      if (r.success) {
        toast(`#${id} → ${STATUS_LABEL[r.status] || r.status}`);
        load();
      }
    } catch (e) { toast(e.message, 'error'); }
  };

  return (
    <div className={`forge-card${embedded ? ' platform-embedded-card' : ''}`} id="platform-sync-jobs">
      <div className="forge-card-title">同步任务</div>
      <p className="platform-section-desc">数据集拉取与 COCO 导出后台作业（与「预测任务」页分开管理）</p>
      <div className="forge-toolbar" style={{ marginBottom: 8 }}>
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => load(jobOffset)}>刷新</button>
      </div>
      <JobsList
        jobs={jobs}
        jobTotal={jobTotal}
        jobOffset={jobOffset}
        pageSize={PAGE_SIZE}
        onPageChange={load}
        detailId={detailId}
        setDetailId={setDetailId}
        onControl={control}
        emptyText="暂无同步任务"
      />
    </div>
  );
}
