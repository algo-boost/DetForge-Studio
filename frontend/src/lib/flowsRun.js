import { STATUS_MAP, statusLabel } from '../components/ui/statusMap';

/** @param {string} runKey e.g. demo:uuid, workflow:9, kestra:exec-id */
export function flowRunPath(runKey) {
  return `/flows/runs/${encodeURIComponent(runKey)}`;
}

/** 将 Kestra 外链转为 Shell 内嵌路径（/ui/main/ 之后部分） */
export function kestraEmbedPath(kestraUrl) {
  if (!kestraUrl) return '';
  const match = String(kestraUrl).match(/\/ui\/[^/]+\/(.+)$/);
  return match ? match[1] : '';
}

export function kestraStudioPath(kestraUrl) {
  const path = kestraEmbedPath(kestraUrl);
  return path ? `/flows/kestra?path=${encodeURIComponent(path)}` : '/flows/kestra';
}

/** 代理模式下 Kestra 执行页相对路径（供内嵌链接，可选） */
export function kestraProxyPath(kestraUrl) {
  const path = kestraEmbedPath(kestraUrl);
  return path ? `/kestra-embed/${path}` : '/kestra-embed/ui/main/flows/iisp';
}

export function parseRunKeyFromParams(searchParams) {
  const run = searchParams.get('run');
  const execution = searchParams.get('execution');
  if (execution) return `kestra:${execution}`;
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
