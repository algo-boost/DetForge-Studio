import { Link } from 'react-router-dom';
import { TODO_STATUS_LABEL } from './homeTypes';

export default function TodoList({ items = [], onResumeKestra }) {
  if (!items.length) {
    return (
      <div className="panel empty-state">
        暂无待办。可从
        {' '}
        <Link to="/query">新建查询</Link>
        {' '}
        或
        {' '}
        <Link to="/flows/demo">编排演示</Link>
        {' '}
        开始。
      </div>
    );
  }

  return (
    <ul className="panel home-list">
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
            {item.kind === 'kestra_pause' && onResumeKestra && (
              <button
                type="button"
                className="btn btn-sm btn-primary home-list-action"
                onClick={() => onResumeKestra(item)}
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
