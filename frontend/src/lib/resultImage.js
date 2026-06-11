import { api } from '../api/client';

/** 预测结果表行是否可用服务端带框预览。 */
export function isPredictResultRow(item, dataSource) {
  return item?.predict_result_id != null || dataSource === 'predict_result';
}

/** 解析结果项图片 URL（预测结果优先带框预览，否则走原图路径）。 */
export function resolveItemImageSrc(item, dataSource) {
  if (item?.predict_result_id != null) {
    return api.forgePredictResultPreviewUrl(item.predict_result_id);
  }
  if (dataSource === 'predict_result' && item?.img_path) {
    return api.imageUrl(item.img_name || '', item.img_path);
  }
  return api.imageUrl(item.img_name, item.img_path);
}
