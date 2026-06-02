import { buildPlatformPages } from './platformUtils';

function StatusPill({ authOk, authConfigured }) {
  if (authOk === true) return <span className="platform-pill platform-pill-ok">平台已连接</span>;
  if (authOk === false) return <span className="platform-pill platform-pill-err">认证失败</span>;
  if (!authConfigured) return <span className="platform-pill platform-pill-warn">未配置认证</span>;
  return <span className="platform-pill platform-pill-ok">已配置</span>;
}

export default function WorkspaceContextBar({
  project,
  datasetCount,
  authOk,
  authConfigured,
  onTestAuth,
}) {
  if (!project) return null;
  const pages = buildPlatformPages(project);

  return (
    <div className="platform-context-bar">
      <div className="platform-context-main">
        <div className="platform-context-project">
          <span className="platform-context-avatar">{project.name?.slice(0, 1) || 'P'}</span>
          <div>
            <div className="platform-context-name">{project.name}</div>
            <div className="platform-context-meta">
              {project.approach_id != null ? `MF Approach ${project.approach_id}` : '未配置 MF Approach'}
              <span className="platform-context-dot">·</span>
              {datasetCount} 个数据集
            </div>
          </div>
        </div>
        <StatusPill authOk={authOk} authConfigured={authConfigured} />
      </div>
      <div className="platform-context-actions">
        {pages && (
          <>
            <a className="platform-context-link" href={pages.datasets} target="_blank" rel="noreferrer">数据集页</a>
            <a className="platform-context-link" href={pages.snapshots} target="_blank" rel="noreferrer">快照页</a>
            <a className="platform-context-link" href={pages.training} target="_blank" rel="noreferrer">训练页</a>
          </>
        )}
        <button type="button" className="btn sm btn-ghost" onClick={onTestAuth}>验证认证</button>
      </div>
    </div>
  );
}
