/** 全站统一状态文案与色调（U4） */
export const STATUS_MAP = {
  pending: { label: '排队', tone: 'neutral' },
  running: { label: '运行中', tone: 'info' },
  waiting_human: { label: '待人工', tone: 'warn' },
  done: { label: '完成', tone: 'success' },
  failed: { label: '失败', tone: 'danger' },
  skipped: { label: '跳过', tone: 'neutral' },
  canceled: { label: '已取消', tone: 'neutral' },
  paused: { label: '已暂停', tone: 'warn' },
};

/** @param {string} status */
export function statusLabel(status, map = STATUS_MAP) {
  return map[status]?.label || status || '—';
}

/** @param {string} status */
export function statusTone(status, map = STATUS_MAP) {
  return map[status]?.tone || 'neutral';
}

/** 工作流运行列表专用文案 */
export const WORKFLOW_RUN_STATUS_MAP = {
  ...STATUS_MAP,
  waiting_human: { label: '待上传 COCO', tone: 'warn' },
};

/** 工作流步骤专用文案 */
export const WORKFLOW_STEP_STATUS_MAP = {
  pending: { label: '待执行', tone: 'neutral' },
  running: { label: '执行中', tone: 'info' },
  done: { label: '完成', tone: 'success' },
  failed: { label: '失败', tone: 'danger' },
  skipped: { label: '已跳过', tone: 'neutral' },
  waiting_human: { label: '待人工', tone: 'warn' },
};

/** 查询任务：running 显示为「执行中」 */
export const QUERY_STATUS_MAP = {
  ...STATUS_MAP,
  running: { label: '执行中', tone: 'info' },
};
