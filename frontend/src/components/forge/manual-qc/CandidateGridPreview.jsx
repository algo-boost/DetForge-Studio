import { ResultImage } from '../../ResultImage';
import { isResultNg, resultStatusLabel } from '../../InspectionResultsLayout';

/**
 * 候选平台图宫格预览，点击进入对照详情。
 */
export default function CandidateGridPreview({
  items,
  activeIndex,
  onSelect,
  customerUrl,
}) {
  if (!items.length) {
    return (
      <div className="mqc-candidate-grid-empty">
        <p>无候选图，请调整筛选或刷新</p>
      </div>
    );
  }

  return (
    <div className="mqc-candidate-grid-wrap">
      {customerUrl && (
        <div className="mqc-candidate-grid-customer">
          <span className="mqc-candidate-grid-label">客户图</span>
          <img src={customerUrl} alt="客户" className="mqc-candidate-grid-customer-img" />
        </div>
      )}
      <div className="mqc-candidate-grid" role="list">
        {items.map((item, i) => {
          const active = i === activeIndex;
          const ng = isResultNg(item);
          const boxN = (item.annotations || []).length;
          return (
            <button
              key={item.id ?? i}
              type="button"
              role="listitem"
              className={`mqc-candidate-grid-card${active ? ' is-active' : ''}`}
              onClick={() => onSelect(i)}
              title={`#${item.id} · ${resultStatusLabel(item.check_status)}`}
            >
              <div className="mqc-candidate-grid-thumb">
                <ResultImage item={item} dataSource="detail" />
                <span className={`mqc-candidate-grid-badge${ng ? ' is-ng' : ' is-ok'}`}>
                  {ng ? 'NG' : 'OK'}
                </span>
                {boxN > 0 && (
                  <span className="mqc-candidate-grid-boxcnt">{boxN} 框</span>
                )}
              </div>
              <div className="mqc-candidate-grid-meta">
                <span className="mqc-candidate-grid-id">#{item.id}</span>
                {item.product_type && (
                  <span className="mqc-candidate-grid-type">{item.product_type}</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
