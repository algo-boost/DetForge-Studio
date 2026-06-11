/** @typedef {'flow_human_gate' | 'workflow_human_gate' | 'manual_qc' | 'curation_batch' | 'kestra_pause'} TodoKind */

/**
 * @typedef {Object} TodoItem
 * @property {string} id
 * @property {TodoKind} kind
 * @property {string} title
 * @property {string} [subtitle]
 * @property {'waiting_human' | 'pending' | 'running'} status
 * @property {string} href
 * @property {string} [created_at]
 * @property {Record<string, unknown>} [meta]
 */

export const TODO_STATUS_LABEL = {
  waiting_human: '待人工',
  pending: '待处理',
  running: '运行中',
};
