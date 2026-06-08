import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { Modal } from './Modal';

const JOB_TYPE_LABEL = {
  predict: '模型预测',
  dataset_sync: '数据集同步',
  manual_qc_archive: '人工质检归档',
  manual_qc_export: '人工质检导出',
};

function jobSummary(job) {
  const type = JOB_TYPE_LABEL[job.job_type] || job.job_type || '后台任务';
  const name = job.name ? `「${job.name}」` : `#${job.id}`;
  const prog = `${job.done + job.failed}/${job.total || job.remaining + job.done + job.failed}`;
  return `${type} ${name} · 进度 ${prog} · 剩余 ${job.remaining}`;
}

export default function ResumeJobsModal() {
  const [jobs, setJobs] = useState([]);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await api.listInterruptedJobs();
      const list = res.jobs || [];
      setJobs(list);
      setOpen(list.length > 0);
    } catch {
      setJobs([]);
      setOpen(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const resolve = async (action) => {
    if (busy || !jobs.length) return;
    setBusy(true);
    try {
      await api.resolveInterruptedJobs({
        action,
        job_ids: jobs.map((j) => j.id),
      });
      setOpen(false);
      setJobs([]);
    } catch (e) {
      window.alert(e.message || '操作失败');
    } finally {
      setBusy(false);
    }
  };

  if (!open || !jobs.length) return null;

  return (
    <Modal open title="检测到未完成的后台任务" wide onClose={() => !busy && resolve('dismiss')}>
      <div className="form-modal-body resume-jobs-modal">
        <p className="resume-jobs-intro">
          服务上次关闭时仍有任务未完成。是否继续执行？选择「暂不继续」将保持暂停，可在
          {' '}
          <Link to="/jobs">任务管理</Link>
          {' '}
          中手动恢复。
        </p>
        <ul className="resume-jobs-list">
          {jobs.map((job) => (
            <li key={job.id}>{jobSummary(job)}</li>
          ))}
        </ul>
        <div className="form-actions">
          <button
            type="button"
            className="btn btn-ghost"
            disabled={busy}
            onClick={() => resolve('dismiss')}
          >
            暂不继续
          </button>
          <button
            type="button"
            className="btn btn-primary"
            disabled={busy}
            onClick={() => resolve('resume')}
          >
            继续执行
          </button>
        </div>
      </div>
    </Modal>
  );
}
