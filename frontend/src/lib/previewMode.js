/** 查询预览模式 */

export function shouldUseFullProcessPreview({ dataSource, hasFlow } = {}) {
  if (hasFlow) return true;
  return dataSource === 'detail';
}
