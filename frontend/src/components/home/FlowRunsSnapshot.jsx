import { Link } from 'react-router-dom';
import HumanGatesPanel from '../flows/HumanGatesPanel';

/**
 * 工作台流水线运行快照：待人工 + 跳转执行历史。
 */
export default function FlowRunsSnapshot({ summary, gateItems = [], onResume }) {
  const waiting = summary?.waiting_human_count ?? gateItems.length;
  const running = summary?.running_flow_count ?? 0;

  return (
    <div className="home-flows-snapshot">
      {gateItems.length > 0 ? (
        <>
          <HumanGatesPanel items={gateItems.slice(0, 4)} onResume={onResume} compact />
          {gateItems.length > 4 && (
            <p className="home-flows-more muted">
              还有 {gateItems.length - 4} 项待处理 ·
              {' '}
              <Link to="/flows?tab=history&status=waiting_human">查看全部</Link>
            </p>
          )}
        </>
      ) : (
        <div className="panel empty-state home-flows-empty">
          无待处理流水线
        </div>
      )}
      <div className="home-flows-links">
        <Link to="/flows?tab=history">全部运行记录</Link>
        {waiting > 0 && (
          <Link to="/flows?tab=history&status=waiting_human">
            {waiting} 待人工
          </Link>
        )}
        {running > 0 && (
          <Link to="/flows?tab=history&status=running">
            {running} 运行中
          </Link>
        )}
      </div>
    </div>
  );
}
