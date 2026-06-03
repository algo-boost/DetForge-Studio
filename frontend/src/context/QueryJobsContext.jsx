import {
  createContext, useCallback, useContext, useEffect, useMemo, useRef, useState,
} from 'react';
import { api, toast } from '../api/client';
import { showErrorModal } from '../lib/errorModal';

const QueryJobsContext = createContext(null);
const POLL_MS = 1500;
const POLL_NETWORK_RETRIES = 40;
const TERMINAL = new Set(['done', 'failed']);

function isNetworkError(err) {
  return err?.isNetwork || /无法连接后端|failed to fetch/i.test(String(err?.message || ''));
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

export function QueryJobsProvider({ children }) {
  const [jobs, setJobs] = useState([]);
  const metaRef = useRef(new Map());
  const pollingRef = useRef(new Set());

  const mergeJob = useCallback((remote) => {
    setJobs((prev) => {
      const idx = prev.findIndex((j) => j.id === remote.id);
      if (idx >= 0) {
        const next = [...prev];
        next[idx] = { ...next[idx], ...remote };
        return next;
      }
      return [remote, ...prev].slice(0, 40);
    });
  }, []);

  const pollJob = useCallback(async (jobId) => {
    if (pollingRef.current.has(jobId)) return;
    pollingRef.current.add(jobId);
    let networkRetries = 0;
    try {
      for (;;) {
        let res;
        try {
          res = await api.getQueryJob(jobId);
          networkRetries = 0;
        } catch (e) {
          if (isNetworkError(e) && networkRetries < POLL_NETWORK_RETRIES) {
            networkRetries += 1;
            await sleep(Math.min(POLL_MS * 2, 4000));
            continue;
          }
          throw e;
        }
        const job = res.job;
        if (!job) break;
        mergeJob(job);
        if (TERMINAL.has(job.status)) {
          const meta = metaRef.current.get(jobId);
          metaRef.current.delete(jobId);
          window.dispatchEvent(new CustomEvent('pc-query-job-finished', {
            detail: { job, meta },
          }));
          if (job.status === 'done') {
            const label = job.label || '查询';
            const n = job.count ?? 0;
            toast(`「${label}」完成 · ${n} 条`, 'success');
          } else {
            showErrorModal(
              job.error || '查询失败',
              { title: `「${job.label || '查询'}」失败` },
            );
          }
          break;
        }
        await sleep(POLL_MS);
      }
    } catch (e) {
      const msg = isNetworkError(e)
        ? '轮询中断：无法连接服务。请打开右下角「查询任务」确认是否已完成，或重新执行。'
        : e.message;
      mergeJob({ id: jobId, status: 'failed', error: msg });
      showErrorModal(msg, { title: '查询任务异常' });
      const meta = metaRef.current.get(jobId);
      metaRef.current.delete(jobId);
      window.dispatchEvent(new CustomEvent('pc-query-job-finished', {
        detail: { job: { id: jobId, status: 'failed', error: msg }, meta },
      }));
    } finally {
      pollingRef.current.delete(jobId);
    }
  }, [mergeJob]);

  const submitQueryJob = useCallback(async (body, { label = '', meta } = {}) => {
    const res = await api.submitQueryJob({ ...body, label });
    if (!res.success) throw new Error(res.error || '提交失败');
    const job = res.job || { id: res.query_job_id, status: 'pending', label };
    mergeJob(job);
    if (meta) metaRef.current.set(job.id, meta);
    pollJob(job.id);
    return job;
  }, [mergeJob, pollJob]);

  const refreshJobs = useCallback(async () => {
    try {
      const res = await api.listQueryJobs({ limit: 30 });
      if (res.success && res.jobs?.length) {
        setJobs(res.jobs);
        res.jobs
          .filter((j) => j.status === 'pending' || j.status === 'running')
          .forEach((j) => pollJob(j.id));
      }
    } catch { /* ignore */ }
  }, [pollJob]);

  useEffect(() => {
    refreshJobs();
  }, [refreshJobs]);

  const runningCount = useMemo(
    () => jobs.filter((j) => j.status === 'pending' || j.status === 'running').length,
    [jobs],
  );

  const value = useMemo(() => ({
    jobs,
    runningCount,
    submitQueryJob,
    refreshJobs,
  }), [jobs, runningCount, submitQueryJob, refreshJobs]);

  return (
    <QueryJobsContext.Provider value={value}>
      {children}
    </QueryJobsContext.Provider>
  );
}

export function useQueryJobs() {
  const ctx = useContext(QueryJobsContext);
  if (!ctx) throw new Error('useQueryJobs must be used within QueryJobsProvider');
  return ctx;
}
