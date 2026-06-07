import { formatDisplayTime } from '../../../lib/timezone';

const FIELD_LABELS = {
  qc_category: '成像情况',
  defect_type: '缺陷类型',
  note: '备注',
  matched_detail_id: '匹配明细',
  matched_img_path: '平台图',
  match_status: '匹配状态',
  disposition: '处置',
  product_type: '产品型号',
};

function fmtVal(v) {
  if (v == null || v === '') return '—';
  if (typeof v === 'string' && v.length > 48) return `${v.slice(0, 48)}…`;
  return String(v);
}

export default function MqcRevisionHistory({ entries = [], loading }) {
  if (loading) {
    return <p className="detail-empty-hint">加载变更历史…</p>;
  }
  if (!entries.length) {
    return <p className="detail-empty-hint">暂无修订记录</p>;
  }

  return (
    <div className="mqc-history-list">
      {entries.map((h) => (
        <details key={h.id} className="mqc-history-item">
          <summary>
            <span className="mqc-history-time">{formatDisplayTime(h.changed_at)}</span>
            <span className="mqc-history-summary">
              {Object.keys(h.changed_fields || {}).length} 项变更
            </span>
          </summary>
          <ul className="mqc-history-changes">
            {Object.entries(h.changed_fields || {}).map(([key, diff]) => (
              <li key={key}>
                <strong>{FIELD_LABELS[key] || key}</strong>
                {'：'}
                <span className="mqc-history-from">{fmtVal(diff?.from)}</span>
                {' → '}
                <span className="mqc-history-to">{fmtVal(diff?.to)}</span>
              </li>
            ))}
          </ul>
          {h.comment && <p className="mqc-history-comment muted">{h.comment}</p>}
        </details>
      ))}
    </div>
  );
}
