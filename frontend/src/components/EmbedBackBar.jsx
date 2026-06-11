import { Link } from 'react-router-dom';
import { PRODUCT_NAME } from '../config/brand';

/**
 * iframe 嵌入页顶栏：返回 IISP 主壳
 */
export default function EmbedBackBar({ returnTo = '/', returnLabel, extra }) {
  return (
    <div className="embed-back-bar" aria-label="嵌入页导航">
      <div className="embed-back-bar-inner">
        <Link className="embed-back-bar-home" to="/">
          ← 返回 {PRODUCT_NAME}
        </Link>
        {returnLabel && returnTo !== '/' && (
          <Link className="embed-back-bar-link" to={returnTo}>
            {returnLabel}
          </Link>
        )}
        {extra}
      </div>
    </div>
  );
}
