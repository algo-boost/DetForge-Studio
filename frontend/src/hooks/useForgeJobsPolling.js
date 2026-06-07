import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';

const ACTIVE_MS = 1500;
const IDLE_MS = 6000;

function hasActiveJobs(jobs) {
  return (jobs || []).some((j) => j.status === 'running' || j.status === 'pending');
}

/**
 * 预测/同步等 forge 作业列表轮询：进行中 1.5s，空闲 6s；切回标签页立即刷新。
 */
export function useForgeJobsPolling(jobType, pageSize = 50, refreshKey = 0) {
  const [jobs, setJobs] = useState([]);
  const [jobOffset, setJobOffset] = useState(0);
  const [jobTotal, setJobTotal] = useState(0);
  const jobsRef = useRef([]);
  const offsetRef = useRef(0);
  const timerRef = useRef(null);
  const mountedRef = useRef(true);

  const load = useCallback(async (off) => {
    const offset = typeof off === 'number' ? off : offsetRef.current;
    try {
      const params = new URLSearchParams();
      if (jobType) params.set('job_type', jobType);
      params.set('limit', String(pageSize));
      params.set('offset', String(offset));
      const j = await api.forgeJobs(`?${params.toString()}`);
      if (!mountedRef.current || !j.success) return;
      const data = j.data || [];
      setJobs(data);
      jobsRef.current = data;
      setJobTotal(j.total || 0);
      setJobOffset(offset);
      offsetRef.current = offset;
    } catch {
      /* 静默轮询失败 */
    }
  }, [jobType, pageSize]);

  useEffect(() => {
    mountedRef.current = true;
    offsetRef.current = 0;

    const schedule = (delay) => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(tick, delay);
    };

    const tick = async () => {
      await load(offsetRef.current);
      if (!mountedRef.current) return;
      schedule(hasActiveJobs(jobsRef.current) ? ACTIVE_MS : IDLE_MS);
    };

    load(0).then(() => {
      if (!mountedRef.current) return;
      schedule(hasActiveJobs(jobsRef.current) ? ACTIVE_MS : IDLE_MS);
    });

    const onVisible = () => {
      if (document.visibilityState !== 'visible') return;
      load(offsetRef.current).then(() => {
        if (mountedRef.current) schedule(ACTIVE_MS);
      });
    };
    document.addEventListener('visibilitychange', onVisible);

    return () => {
      mountedRef.current = false;
      clearTimeout(timerRef.current);
      document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load, refreshKey]);

  return { jobs, jobTotal, jobOffset, load };
}
