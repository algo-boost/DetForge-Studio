import { STATUS_MAP, statusLabel } from '../components/ui/statusMap';

/** @param {string} runKey e.g. demo:uuid, workflow:9 */
export function flowRunPath(runKey) {
  return `/flows/runs/${encodeURIComponent(runKey)}`;
}

/** 组合编排 flow_* / custom_* 模板 */
export function isForgeComposeFlowId(flowId) {
  const fid = String(flowId || '');
  return fid.startsWith('flow_') || fid.startsWith('custom_');
}

/** 任务详情链接：custom_* / flow_* → 组合编排页（带 flow 参数） */
export function flowTaskPath(flowId, source) {
  if (source === 'workflow' || isForgeComposeFlowId(flowId)) {
    const fid = String(flowId || '');
    if (fid.startsWith('flow_') && fid !== 'flow_draft') {
      return `/flows/compose?flow=${encodeURIComponent(fid)}`;
    }
    return '/flows/compose';
  }
  return `/flows/tasks/${encodeURIComponent(flowId)}`;
}

export function parseRunKeyFromParams(searchParams) {
  const run = searchParams.get('run');
  if (run) return run.includes(':') ? run : `workflow:${run}`;
  return null;
}

export const RUN_STATUS_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'waiting_human', label: '待人工' },
  { value: 'running', label: '运行中' },
  { value: 'done', label: '完成' },
  { value: 'failed', label: '失败' },
];

/** @deprecated 使用 statusLabel 或 StatusPill */
export const RUN_STATUS_LABEL = Object.fromEntries(
  Object.entries(STATUS_MAP).map(([k, v]) => [k, v.label]),
);

export { statusLabel, STATUS_MAP };
