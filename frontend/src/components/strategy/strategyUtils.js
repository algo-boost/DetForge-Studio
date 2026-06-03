export const STRATEGY_EDITOR_TABS = [
  { id: 'meta', label: '基本信息', desc: '名称与模式' },
  { id: 'params', label: '可调参数', desc: '中文名与默认值' },
  { id: 'sql', label: 'SQL 模板', desc: '数据拉取' },
  { id: 'rules', label: '筛选规则', desc: 'Pipeline 规则表' },
  { id: 'code', label: 'process_data', desc: 'Python 后处理' },
  { id: 'flow', label: 'Flow JSON', desc: '只读预览' },
];

export const FILTER_MODE_LABEL = {
  rules: '仅规则',
  code: '仅代码',
  split: '仅规则',
};

export function isBuiltinStrategy() {
  return false;
}

export function isPresetStrategy() {
  return false;
}
