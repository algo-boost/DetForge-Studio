import { Link } from 'react-router-dom';
import { TODO_STATUS_LABEL } from '../home/homeTypes';

export default function HumanGatesPanel({ items = [], onResume, compact = false }) {
  if (!items.length) {
    return (
      <div className="empty-state">
        暂无人工卡点
      </div>
    );
  }

  const canResume = (item) => (
    item.kind === 'workflow_human_gate' || item.kind === 'flow_human_gate'
  );

  return (
    <ul className={`panel home-list${compact ? ' home-list--compact' : ''}`}>
      {items.map((item) => (
        <li key={item.id} className="home-list-item">
          <div className="home-list-row">
            <Link to={item.href} className="home-list-link">
              <div className="home-list-title">{item.title}</div>
              {item.subtitle && (
                <div className="home-list-subtitle">{item.subtitle}</div>
              )}
              <div className="home-list-status">
                {TODO_STATUS_LABEL[item.status] || item.status}
              </div>
            </Link>
            {canResume(item) && onResume && (
              <button
                type="button"
                className="btn btn-sm btn-primary home-list-action"
                onClick={() => onResume(item)}
              >
                继续
              </button>
            )}
          </div>
        </li>
      ))}
    </ul>
  );
}
