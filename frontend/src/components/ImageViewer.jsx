import { useEffect, useRef } from 'react';
import { getProductNo, getProductType } from '../lib/resultFilters';
import { isPredictResultRow, resolveItemImageSrc } from '../lib/resultImage';
import { formatDisplayTime } from '../lib/timezone';

export function ImageViewer({ items, index, selected, onClose, onNav, onToggleSelect, dataSource = 'detail' }) {
  const item = items[index];
  const canvasRef = useRef(null);
  const predictPreview = isPredictResultRow(item, dataSource);

  useEffect(() => {
    const onKey = (e) => {
      if (e.key === 'Escape') onClose();
      if (e.key === 'ArrowLeft' && index > 0) onNav(index - 1);
      if (e.key === 'ArrowRight' && index < items.length - 1) onNav(index + 1);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [index, items.length, onClose, onNav]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !item) return;
    const img = new Image();
    img.onload = () => {
      canvas.width = img.naturalWidth;
      canvas.height = img.naturalHeight;
      const ctx = canvas.getContext('2d');
      ctx.drawImage(img, 0, 0);
      if (!predictPreview) {
        (item.annotations || []).forEach((ann) => {
          const [x, y, w, h] = ann.bbox || [];
          if (w == null) return;
          ctx.strokeStyle = '#ef4444';
          ctx.lineWidth = 2;
          ctx.strokeRect(x, y, w, h);
          ctx.fillStyle = 'rgba(239,68,68,0.85)';
          ctx.font = '14px sans-serif';
          ctx.fillText(`${ann.category || ''} ${(ann.score ?? 0).toFixed(2)}`, x, Math.max(12, y - 4));
        });
      }
    };
    img.src = resolveItemImageSrc(item, dataSource);
  }, [item, predictPreview, dataSource]);

  if (!item) return null;
  const rawIdx = item.__rawIndex ?? index;
  const isSel = selected.has(rawIdx);

  return (
    <div className="imodal" style={{ display: 'block' }}>
      <div className="imodal-content">
        <div className="imodal-left">
          <button type="button" className="imodal-btn imodal-close" onClick={onClose}>✕</button>
          <canvas ref={canvasRef} className="imodal-img" />
          <button type="button" className="imodal-nav imodal-prev" disabled={index <= 0} onClick={() => onNav(index - 1)}>‹</button>
          <button type="button" className="imodal-nav imodal-next" disabled={index >= items.length - 1} onClick={() => onNav(index + 1)}>›</button>
          <div className="imodal-info-bar">
            <span>{index + 1} / {items.length}</span>
            <span>{item.img_name}</span>
          </div>
        </div>
        <div className="imodal-right">
          <div className="imodal-meta">
            <div className="imeta-row"><span className="imeta-label">文件名</span><span>{item.img_name}</span></div>
            <div className="imeta-row"><span className="imeta-label">时间</span><span>{formatDisplayTime(item.c_time)}</span></div>
            {getProductType(item) && (
              <div className="imeta-row"><span className="imeta-label">型号</span><span>{getProductType(item)}</span></div>
            )}
            {getProductNo(item) && (
              <div className="imeta-row"><span className="imeta-label">SN</span><span>{getProductNo(item)}</span></div>
            )}
            {item.product_id && item.product_id !== getProductNo(item) && (
              <div className="imeta-row"><span className="imeta-label">产品 ID</span><span>{item.product_id}</span></div>
            )}
            {item.position && (
              <div className="imeta-row"><span className="imeta-label">部位</span><span>{item.position}</span></div>
            )}
            <div className="imeta-row"><span className="imeta-label">检测</span><span>{item.detection_result_status}</span></div>
            <div className="imeta-row"><span className="imeta-label">人工</span><span>{item.manual_check_status}</span></div>
            <div className="imeta-row"><span className="imeta-label">状态</span><span>{item.check_status === '1' ? 'NG' : 'OK'}</span></div>
          </div>
          <button type="button" className="btn btn-primary" onClick={() => onToggleSelect(rawIdx)}>{isSel ? '取消选中' : '选中'}</button>
        </div>
      </div>
    </div>
  );
}
