/** IISP Shell 内集成：直接 lazy 路由；独立部署见 tools/query/ui/ */
export const QUERY_UI_MOUNT = '/tools/query';

export const queryToolRoutes = [
  { path: 'query', label: '数据查询' },
  { path: 'query-results', label: '查询结果' },
  { path: 'history', label: '查询历史' },
  { path: 'strategies', label: '查询策略' },
];

export default queryToolRoutes;
