import { zonedParts } from '../../../lib/timezone';

export const MQC_TABS = [
  { id: 'intake', label: '登记入队', desc: '导入客户图与 SN' },
  { id: 'review', label: '核对确认', desc: '对比平台图·分类归档' },
  { id: 'library', label: '归档库', desc: '已定案·导出·交接' },
  { id: 'settings', label: '类别设置', desc: '成像/缺陷配置' },
];

export const MATCH_LABEL = {
  matched: '已匹配',
  not_found: '未匹配',
  multiple: '多条候选',
  pending: '待匹配',
};

export const TRAINING_LABEL = {
  pending: '待交接',
  handoff_ready: '已交接',
  closed: '已关闭',
};

export function todayBatchId() {
  const p = zonedParts();
  const pad = (n) => String(n).padStart(2, '0');
  return `${p.year}-${pad(p.month)}-${pad(p.day)}`;
}

export const MATCH_PILL_CLASS = {
  matched: 'mqc-pill mqc-pill-ok',
  not_found: 'mqc-pill mqc-pill-warn',
  multiple: 'mqc-pill mqc-pill-info',
};

/** 平台明细 → 查询结果视图 item（筛选 / DetailImageStage 共用） */
export function normalizePlatformRecord(record, index = 0) {
  if (!record) return null;
  const id = record.id;
  return {
    ...record,
    id,
    img_path: record.img_path || '',
    img_name: String(id),
    product_no: record.product_no || '',
    check_status: String(record.check_status ?? ''),
    detection_result_status: String(record.detection_result_status ?? ''),
    annotations: record.annotations || [],
    box_count: record.box_count ?? (record.annotations || []).length,
    __rawIndex: index,
  };
}
