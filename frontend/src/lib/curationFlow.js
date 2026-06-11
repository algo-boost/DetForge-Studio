/** 筛选批次（①②）统一四步闭环 */

export const INTENT_LABEL = {
  daily_ng: '每日 NG 捞',
  replay_eval: '历史回跑',
  customer_qc: '人工质检',
};

export const STATUS_LABEL = {
  created: '待出站',
  exported: '待回传 COCO',
  imported: '待归档',
  archived: '待交接',
  handoff_ready: '交接就绪',
  handoff_done: '已交接',
  closed: '已关闭',
};

export const FLOW_STEPS = [
  { key: 'export', label: '出站' },
  { key: 'import', label: '回传 COCO' },
  { key: 'archive', label: '归档' },
  { key: 'handoff', label: '交接' },
];

export function flowStepIndex(status) {
  const map = {
    created: 0,
    exported: 1,
    imported: 2,
    archived: 3,
    handoff_ready: 4,
    handoff_done: 5,
    closed: 5,
  };
  return map[status] ?? 0;
}

export function nextBatchAction(status) {
  switch (status) {
    case 'created':
      return { key: 'export', label: '生成出站包', hint: '导出 COCO + 图片，供外部工具筛选' };
    case 'exported':
      return { key: 'import', label: '上传筛选后的 COCO', hint: '外部删图/改标注后，回传 _annotations.coco.json' };
    case 'imported':
      return { key: 'archive_handoff', label: '归档并生成交接包', hint: '一步完成归档 + training_inbox 交接' };
    case 'archived':
      return { key: 'handoff', label: '生成交接包', hint: '输出到 datasets/training_inbox/' };
    case 'handoff_ready':
      return { key: 'done', label: '标记已交接', hint: '训练侧已领取后可关闭批次' };
    default:
      return null;
  }
}

export const DISPOSITION_LABEL = {
  ng_confirmed: '确认 NG',
  need_label: '待打标',
  fp_model: '误检',
  fn_missed: '漏检',
  tp_detected: '已检出',
  qc_no_shot: '拍不到',
  qc_blur: '成像不清',
  qc_matched: '已对齐',
  rejected: '已剔除',
};
