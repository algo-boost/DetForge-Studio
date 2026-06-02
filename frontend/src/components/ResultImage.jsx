import { useEffect, useState } from 'react';
import { appendApiToken } from '../api/client';
import { isPredictResultRow, resolveItemImageSrc } from '../lib/resultImage';

export function ResultImage({ item, className = '', onLoad, dataSource = 'detail' }) {
  const [failed, setFailed] = useState(false);
  const [src, setSrc] = useState(() => resolveItemImageSrc(item, dataSource));
  const [usedFallback, setUsedFallback] = useState(false);

  useEffect(() => {
    setFailed(false);
    setUsedFallback(false);
    setSrc(resolveItemImageSrc(item, dataSource));
  }, [item, dataSource]);

  const tryFallback = () => {
    if (usedFallback || !item?.img_path) return false;
    if (isPredictResultRow(item, dataSource) && item.predict_result_id != null) {
      const name = item.img_name || '';
      setSrc(appendApiToken(
        `/api/image/${encodeURIComponent(name)}?path=${encodeURIComponent(item.img_path)}`,
      ));
      setUsedFallback(true);
      return true;
    }
    return false;
  };

  if (failed) {
    return (
      <div className={`img-load-failed${className ? ` ${className}` : ''}`} title="图片加载失败">
        <span>无法加载</span>
      </div>
    );
  }
  return (
    <img
      className={className || undefined}
      src={src}
      alt=""
      loading="lazy"
      onLoad={onLoad}
      onError={() => { if (!tryFallback()) setFailed(true); }}
    />
  );
}
