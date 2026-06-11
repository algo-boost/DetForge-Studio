/** 策略默认数据源推断 */

export const STRATEGY_DATA_SOURCES = [
  { id: 'predict_result', label: '预测结果' },
  { id: 'detail', label: '明细表' },
];

export function inferDataSourceFromStrategy(strategy) {
  const ds = strategy?.data_source || strategy?.default_data_source;
  if (ds) return ds;
  const sql = String(strategy?.sql || strategy?.detail_sql || '');
  if (sql.includes('product_detection_detail_result')) return 'detail';
  return 'predict_result';
}

export function parseDefaultPredictJobId(strategy) {
  const v = strategy?.default_predict_job_id ?? strategy?.predict_job_id;
  if (v == null || v === '') return null;
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : null;
}
