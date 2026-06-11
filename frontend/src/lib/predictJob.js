/** 预测批次 job 展示与解析 */

/** 从 SQL 文本解析 job_id。 */
export function parsePredictJobIdFromSql(sql) {
  const m = String(sql || '').match(/\bjob_id\s*=\s*(\d+)/i);
  return m ? Number(m[1]) : null;
}

/** 作业列表项上的模型名（params / name 解析）。 */
export function predictJobModelName(job) {
  if (!job) return '';
  const params = job.params || {};
  if (params.model_name) return String(params.model_name);
  const name = String(job.name || '');
  const sep = name.indexOf(' · ');
  if (sep > 0) return name.slice(sep + 3).trim();
  return '';
}

/** 下拉 / 提示用单行标签。 */
export function formatPredictJobLabel(job) {
  if (!job) return '';
  const model = predictJobModelName(job);
  const progress = `${job.done ?? '?'}/${job.total ?? '?'}`;
  const modelPart = model ? ` · ${model}` : '';
  return `#${job.id}${modelPart} · ${progress} 张`;
}

/** 拉取最近预测作业（优先已完成，否则含进行中）。 */
export async function fetchRecentPredictJobs(api, limit = 20) {
  const done = await api.forgeJobs(`?job_type=predict&status=done&limit=${limit}`);
  if (done.success && done.data?.length) return done.data;
  const any = await api.forgeJobs(`?job_type=predict&limit=${limit}`);
  return any.success ? (any.data || []) : [];
}

/**
 * 自动匹配预测批次 ID：
 * 1. URL ?predict_job=
 * 2. 最近完成的预测作业（默认）
 * 3. SQL 里已有的 job_id
 */
export async function resolvePredictJobId({ urlJobId, sql, recentJobs, fetchJobs } = {}) {
  if (urlJobId != null && /^\d+$/.test(String(urlJobId))) {
    return Number(urlJobId);
  }
  const jobs = recentJobs || (fetchJobs ? await fetchJobs() : []);
  if (jobs.length) return jobs[0].id;
  return parsePredictJobIdFromSql(sql);
}
