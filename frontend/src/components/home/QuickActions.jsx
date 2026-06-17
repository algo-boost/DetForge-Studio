import { Link } from 'react-router-dom';
import { useUserPrefs } from '../../context/UserPrefsContext';
import { USER_TIERS } from '../../config/nav';

export default function QuickActions({ busy, onSyncCatalog }) {
  const { tier } = useUserPrefs();
  const isConfigurer = tier === USER_TIERS.CONFIGURER;

  return (
    <div className="home-quick-actions">
      <Link to="/query" className="btn primary">新建查询</Link>
      {isConfigurer && (
        <>
          <button type="button" className="btn" disabled={busy} onClick={onSyncCatalog}>
            同步 Catalog
          </button>
          <Link to="/flows/demo" className="btn">编排演示</Link>
          <Link to="/flows/compose" className="btn">流水线</Link>
        </>
      )}
      {!isConfigurer && (
        <>
          <Link to="/manual-qc" className="btn">人工质检</Link>
          <Link to="/jobs" className="btn">预测任务</Link>
        </>
      )}
    </div>
  );
}
