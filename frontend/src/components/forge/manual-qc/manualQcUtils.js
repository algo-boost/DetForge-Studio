export const MQC_TABS = [
  { id: 'archive', label: '核对归档', desc: '单条客户图匹配' },
  { id: 'batch', label: '批量归档', desc: '多图逐条填 SN' },
  { id: 'query', label: '查询导出', desc: '时段筛选与导出' },
  { id: 'records', label: '最近记录', desc: '编辑与对比' },
  { id: 'settings', label: '类别设置', desc: '成像/缺陷配置' },
];

export const MATCH_LABEL = { matched: '已匹配', not_found: '未匹配', multiple: '多条候选' };

export const MATCH_PILL_CLASS = {
  matched: 'mqc-pill mqc-pill-ok',
  not_found: 'mqc-pill mqc-pill-warn',
  multiple: 'mqc-pill mqc-pill-info',
};
