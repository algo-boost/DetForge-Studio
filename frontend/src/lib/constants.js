export const DEFAULT_DETAIL_SQL = "SELECT * FROM product_detection_detail_result\nWHERE check_status = '1'\n  AND c_time BETWEEN '${START_TIME}' AND '${END_TIME}'";
export const DEFAULT_PREDICT_SQL = 'SELECT * FROM `detforge`.`predict_result`';
/** 查询页默认 SQL（预测结果表） */
export const DEFAULT_SQL = DEFAULT_PREDICT_SQL;

/** 按预测作业批次生成 SQL（仅 job_id，不限时间段） */
export function buildPredictJobSql(table, jobId) {
  const t = table || '`detforge`.`predict_result`';
  if (jobId != null && String(jobId).trim() !== '') {
    return `SELECT * FROM ${t}\nWHERE job_id = ${Number(jobId)}`;
  }
  return `SELECT * FROM ${t}`;
}
export const DEFAULT_PY = `def process_data(df):
    df = apply_filter_rules(df)
    return df`;

export const RULES_CODE_PLACEHOLDER = '# 添加规则后将自动生成 apply_filter_rules(df)';
export const DEFAULT_SAMPLE = 300;
export const DEFAULT_SEED = 42;
export const PREVIEW_LIMIT = 5;
export const PAGE_SIZE = 24;
export const LARGE_RESULT_THRESHOLD = 500;
export const DEFAULT_RESULTS_HEIGHT = 520;

export function buildSampleFunction(sampleSize = DEFAULT_SAMPLE, randomSeed = DEFAULT_SEED) {
  return `def apply_random_sample_rows(df, max_rows=${sampleSize}, random_seed=${randomSeed}):
    """随机采样；行数不足时返回全部。"""
    max_rows = int(max_rows)
    seed = int(random_seed)
    if max_rows <= 0 or len(df) <= max_rows:
        return df.reset_index(drop=True)
    return df.sample(n=max_rows, random_state=seed).reset_index(drop=True)`;
}
