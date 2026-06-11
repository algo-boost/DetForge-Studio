/**
 * 工具集成注册表 — ToolHost / useToolIntegration 共用。
 * statusPath 优先走 /api/tools/{id}/integration；legacyStatusPath 兼容旧端点。
 */
export const TOOL_INTEGRATION_REGISTRY = {
  query: {
    toolId: 'query',
    statusPath: '/api/tools/query/integration',
    legacyStatusPath: '/api/query-tool/status',
    defaultMount: '/tools/query',
    routing: 'hash',
    title: '数据查询',
    loadingLabel: '正在加载数据查询…',
    remoteLoadingLabel: '正在连接 Query 服务…',
  },
  viz: {
    toolId: 'viz',
    statusPath: '/api/tools/viz/integration',
    legacyStatusPath: '/api/viz/status',
    defaultMount: '/viz',
    routing: 'path',
    title: '样本图库',
    loadingLabel: '正在加载样本图库…',
    remoteLoadingLabel: '正在连接 COCO 可视化…',
  },
  unify: {
    toolId: 'unify',
    statusPath: '/api/tools/unify/integration',
    legacyStatusPath: '/api/unify/status',
    defaultMount: '/unify',
    routing: 'path',
    title: 'DetUnify',
    loadingLabel: '正在加载 DetUnify…',
    remoteLoadingLabel: '正在连接 DetUnify…',
  },
};

export function getToolIntegrationSpec(toolId) {
  const spec = TOOL_INTEGRATION_REGISTRY[toolId];
  if (!spec) {
    return {
      toolId,
      statusPath: `/api/tools/${toolId}/integration`,
      legacyStatusPath: null,
      defaultMount: `/tools/${toolId}`,
      routing: 'hash',
      title: toolId,
      loadingLabel: '加载中…',
      remoteLoadingLabel: '正在连接…',
    };
  }
  return spec;
}
