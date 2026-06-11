import { Link } from 'react-router-dom';

export default function ActiveFlowsPanel({ flows = [] }) {
  if (!flows.length) {
    return (
      <div className="panel empty-state">无 Flow 卡点</div>
    );
  }

  return (
    <ul className="panel home-list">
      {flows.map((f) => (
        <li key={f.run_id} className="home-list-item home-list-item--compact">
          {f.source === 'kestra' ? (
            <>
              <div className="home-list-title">{f.flow_id || f.run_id}</div>
              <div className="home-list-status">
                Kestra · {f.batch_id ? `batch ${f.batch_id}` : f.run_id}
              </div>
            </>
          ) : (
            <>
              <Link to={flowRunPath(`demo:${f.run_id}`)} className="home-list-title">
                {f.flow_id || f.run_id}
              </Link>
              <div className="home-list-status">{f.pause_at}</div>
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
