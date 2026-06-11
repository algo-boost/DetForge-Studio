/** 样本图库打开失败时的可读提示 */
export function formatSampleGalleryError(err, context = '') {
  const msg = String(err?.message || err || '未知错误').trim();
  const ctx = context ? `（${context}）` : '';

  if (/作业不存在|job.*not found/i.test(msg)) {
    return `预测作业不存在或已删除${ctx}。请刷新预测任务列表后重试。`;
  }
  if (/没有符合条件|无.*预测结果|no.*result/i.test(msg)) {
    return `该批次尚无可用预测结果${ctx}。请确认作业已完成，或放宽筛选条件。`;
  }
  if (/viz|COCOVisualizer|图库.*不可用|not available/i.test(msg)) {
    return `样本图库未就绪${ctx}。请在设置中配置 coco_visualizer_root 并重启 Flask。`;
  }
  if (/路径|path|不存在|not found|ENOENT/i.test(msg)) {
    return `图片或 COCO 文件路径不可读${ctx}。请检查 exports/ 目录与图片根路径配置。`;
  }
  if (/导出|export/i.test(msg)) {
    return `导出样本图库数据失败${ctx}：${msg}`;
  }
  return msg ? `${msg}${ctx}` : `打开样本图库失败${ctx}`;
}
