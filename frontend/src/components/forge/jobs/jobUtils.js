export const STATUS_LABEL = {
  pending: '排队',
  running: '运行中',
  paused: '已暂停',
  done: '完成',
  failed: '失败',
  canceled: '已取消',
};

export const STATUS_PILL_CLASS = {
  pending: 'pjobs-pill pjobs-pill-muted',
  running: 'pjobs-pill pjobs-pill-active',
  paused: 'pjobs-pill pjobs-pill-warn',
  done: 'pjobs-pill pjobs-pill-ok',
  failed: 'pjobs-pill pjobs-pill-err',
  canceled: 'pjobs-pill pjobs-pill-muted',
};

export const JOBS_TABS = [
  { id: 'list', label: '作业列表', desc: '进度与详情' },
  { id: 'create', label: '新建预测', desc: '单模型作业' },
];

export const IMAGE_SOURCE_OPTIONS = [
  { id: 'task', label: '查询任务', desc: '使用查询页导出的 task_id' },
  { id: 'dir', label: '图片目录', desc: '本地绝对路径' },
  { id: 'paths', label: '路径列表', desc: '逐行指定图片路径' },
];
