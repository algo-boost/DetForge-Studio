import { zonedParts } from '../../../lib/timezone';

export const MQC_TABS = [
  { id: 'archive', label: '核对归档', desc: '单条客户图匹配' },
  { id: 'batch', label: '批量归档', desc: '多图逐条填 SN' },
  { id: 'library', label: '归档库', desc: '按日查看·导出·交接' },
  { id: 'settings', label: '类别设置', desc: '成像/缺陷配置' },
];

export const MATCH_LABEL = { matched: '已匹配', not_found: '未匹配', multiple: '多条候选' };

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
