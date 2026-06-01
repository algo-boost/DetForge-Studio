export default function ProjectSidebar({
  projects,
  selectedProject,
  onSelectProject,
  onDeleteProject,
  onNewProject,
  onEditProject,
  currentProject,
}) {
  return (
    <aside className="platform-sidebar">
      <div className="platform-sidebar-head">
        <div className="platform-sidebar-title">项目</div>
        <p className="platform-sidebar-sub">Magic-Fox 训练平台本地工作区</p>
      </div>

      <div className="platform-sidebar-section">
        {!projects.length ? (
          <p className="platform-sidebar-empty">暂无项目</p>
        ) : (
          <div className="platform-project-list">
            {projects.map((p) => (
              <button
                key={p.id}
                type="button"
                className={`platform-project-item${selectedProject === p.id ? ' is-on' : ''}`}
                onClick={() => onSelectProject(p.id)}
              >
                <span className="platform-project-item-avatar">{p.name?.slice(0, 1) || '?'}</span>
                <span className="platform-project-item-body">
                  <span className="platform-project-item-name">{p.name}</span>
                  <span className="platform-project-item-meta">
                    {p.approach_id != null ? `MF ${p.approach_id}` : '待配置 MF Approach'}
                  </span>
                </span>
                <span
                  className="platform-project-item-del"
                  role="button"
                  tabIndex={0}
                  title="删除项目"
                  onClick={(e) => { e.stopPropagation(); onDeleteProject(p.id); }}
                  aria-label="删除"
                >
                  ×
                </span>
              </button>
            ))}
          </div>
        )}
        <div className="platform-sidebar-actions">
          <button type="button" className="btn sm primary block" onClick={onNewProject}>新建项目</button>
          {currentProject && (
            <button type="button" className="btn sm block" onClick={() => onEditProject(currentProject)}>编辑当前项目</button>
          )}
        </div>
      </div>

      <div className="platform-sidebar-tip">
        <div className="platform-sidebar-tip-title">使用提示</div>
        <ul>
          <li>先在侧栏选择项目，再用顶部 Tab 切换工作区</li>
          <li>发现导入可批量添加底库与快照</li>
          <li>预测任务在「预测任务」页查看进度</li>
        </ul>
      </div>
    </aside>
  );
}
