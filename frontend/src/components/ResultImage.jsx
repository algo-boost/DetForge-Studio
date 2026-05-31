import { useState } from 'react';
import { resolveItemImageSrc } from '../lib/resultImage';

export function ResultImage({ item, className = '', onLoad, dataSource = 'detail' }) {
  const [failed, setFailed] = useState(false);
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
      src={resolveItemImageSrc(item, dataSource)}
      alt=""
      loading="lazy"
      onLoad={onLoad}
      onError={() => setFailed(true)}
    />
  );
}
