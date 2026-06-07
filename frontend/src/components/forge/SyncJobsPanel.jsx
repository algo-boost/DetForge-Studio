import { useState } from 'react';
import { api, toast } from '../../api/client';
import { STATUS_LABEL } from './JobWidgets';
import JobsList from './JobsList';
import { useForgeJobsPolling } from '../../hooks/useForgeJobsPolling';

const PAGE_SIZE = 50;

export default function SyncJobsPanel({ refreshKey = 0, embedded = false }) {
  const [detailId, setDetailId] = useState(null);
  const { jobs, jobTotal, jobOffset, load } = useForgeJobsPolling('dataset_sync', PAGE_SIZE, refreshKey);

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
