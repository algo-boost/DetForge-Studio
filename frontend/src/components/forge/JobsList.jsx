import { Fragment } from 'react';
import { Link } from 'react-router-dom';
import { ProgressBar, JobDetail } from './JobWidgets';
import StatusPill from '../ui/StatusPill';

function JobEmptyActions() {
  return (
    <div className="pjobs-empty-actions">
      <Link className="btn btn-sm btn-primary" to="/online-predict">发起批量预测</Link>
      <Link className="btn btn-sm btn-ghost" to="/models">管理模型</Link>
      <Link className="btn btn-sm btn-ghost" to="/training">训练平台</Link>
    </div>
  );
}

function JobActions({ job, detailId, setDetailId, onControl }) {
  const isExpanded = detailId === job.id;
  return (
    <div className="pjobs-row-actions">
      <button type="button" className={`btn btn-sm ${isExpanded ? 'btn-primary' : 'btn-ghost'}`} onClick={() => setDetailId(isExpanded ? null : job.id)}>
        {isExpanded ? '收起' : '详情'}
      </button>
      {(job.status === 'running' || job.status === 'pending') && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onControl(job.id, 'pause')}>暂停</button>
      )}
      {(job.status === 'paused' || job.status === 'failed' || job.status === 'canceled') && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onControl(job.id, 'resume')}>继续</button>
      )}
      {job.failed > 0 && (
        <button type="button" className="btn btn-sm btn-ghost" onClick={() => onControl(job.id, 'retry')}>重试失败</button>
      )}
      {job.status !== 'done' && job.status !== 'canceled' && (
        <button type="button" className="btn btn-sm btn-ghost pjobs-action-danger" onClick={() => onControl(job.id, 'cancel')}>取消</button>
      )}
    </div>
  );
}

export default function JobsList({
  jobs,
  jobTotal,
  jobOffset,
  pageSize,
  onPageChange,
  detailId,
  setDetailId,
  onControl,
  showType = false,
  emptyText = '暂无作业',
}) {
  if (!jobs.length) {
    return (
      <div className="pjobs-empty-state">
        <p>{emptyText}</p>
        <JobEmptyActions />
      </div>
    );
  }

  return (
    <>
      <div className="pjobs-table-wrap">
        <table className="models-table pjobs-table">
          <thead>
            <tr>
              <th>#</th>
              <th>名称</th>
              {showType && <th>类型</th>}
              <th>状态</th>
              <th>进度</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <Fragment key={job.id}>
                <tr className={detailId === job.id ? 'is-expanded' : ''}>
                  <td className="pjobs-id">{job.id}</td>
                  <td className="pjobs-name">{job.name || '—'}</td>
                  {showType && <td>{job.job_type}</td>}
                  <td><StatusPill status={job.status} /></td>
                  <td><ProgressBar job={job} /></td>
                  <td>
                    <JobActions job={job} detailId={detailId} setDetailId={setDetailId} onControl={onControl} />
                  </td>
                </tr>
                {detailId === job.id && (
                  <tr className="pjobs-detail-row">
                    <td colSpan={showType ? 6 : 5}>
                      <JobDetail job={job} />
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
      {jobTotal > pageSize && (
        <div className="pjobs-pager">
          <span className="muted">共 {jobTotal} 条 · 当前 {jobOffset + 1}–{Math.min(jobOffset + jobs.length, jobTotal)}</span>
          <span className="pjobs-pager-btns">
            <button type="button" className="btn btn-sm btn-ghost" disabled={jobOffset <= 0} onClick={() => onPageChange(Math.max(0, jobOffset - pageSize))}>上一页</button>
            <button type="button" className="btn btn-sm btn-ghost" disabled={jobOffset + pageSize >= jobTotal} onClick={() => onPageChange(jobOffset + pageSize)}>下一页</button>
          </span>
        </div>
      )}
    </>
  );
}
