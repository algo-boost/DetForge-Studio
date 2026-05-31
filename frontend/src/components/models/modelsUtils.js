export const MODELS_TABS = [
  { id: 'registry', label: '注册表', desc: '本地已登记模型' },
  { id: 'platform', label: '训练平台', desc: 'Magic-Fox 线上模型' },
  { id: 'deploy', label: '部署模型', desc: 'DB 部署权重' },
  { id: 'train', label: '训练配置', desc: 'DB 训练记录' },
];

export const SOURCE_LABEL = {
  manual: '手动',
  modeldeploy: '部署导入',
  modeltrainconfig: '训练导入',
  platform: '训练平台',
};

export const SOURCE_PILL_CLASS = {
  manual: 'models-pill models-pill-info',
  modeldeploy: 'models-pill models-pill-ok',
  modeltrainconfig: 'models-pill models-pill-warn',
  platform: 'models-pill models-pill-active',
};
