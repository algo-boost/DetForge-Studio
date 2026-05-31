import { Link } from 'react-router-dom';

const WORKFLOW = [
  { step: 1, title: '连接平台', desc: '在设置页配置 Magic-Fox 认证', tab: null, action: 'config' },
  { step: 2, title: '发现 / 导入', desc: '粘贴 Magic-Fox URL，批量导入底库与快照', tab: 'discover' },
  { step: 3, title: '同步数据集', desc: '拉取图片与 COCO 标注到本地', tab: 'datasets' },
  { step: 4, title: '模型预测', desc: '多选线上部署 / 训练模型，对本地数据批量预测', tab: 'predict' },
  { step: 5, title: '查看结果', desc: '同步任务在本页；预测结果在「预测任务」页与查询页', tab: 'jobs', link: '/jobs' },
];

export default function PlatformOverview({
  project,
  datasets,
  onNavigate,
  onSyncAll,
  syncingAll,
}) {
  const syncedCount = datasets.filter((d) => d.last_sync_at).length;
  const enabledCount = datasets.filter((d) => d.enabled !== 0).length;

  return (
    <div className="platform-overview">
      <div className="platform-stat-grid">
        <div className="platform-stat-card platform-stat-card-accent">
          <div className="platform-stat-card-val">{datasets.length}</div>
          <div className="platform-stat-card-label">已配置数据集</div>
        </div>
        <div className="platform-stat-card">
          <div className="platform-stat-card-val">{syncedCount}</div>
          <div className="platform-stat-card-label">曾同步过</div>
        </div>
        <div className="platform-stat-card">
          <div className="platform-stat-card-val">{enabledCount}</div>
          <div className="platform-stat-card-label">启用中</div>
        </div>
        <div className="platform-stat-card platform-stat-card-action">
          <button type="button" className="btn primary" disabled={!datasets.length || syncingAll} onClick={onSyncAll}>
            {syncingAll ? '提交中…' : '全部同步'}
          </button>
          <div className="platform-stat-card-label">一键提交所有数据集同步任务</div>
        </div>
        <div className="platform-stat-card platform-stat-card-action">
          <button type="button" className="btn" onClick={() => onNavigate('predict')} disabled={!datasets.length}>
            去预测
          </button>
          <div className="platform-stat-card-label">对本地数据创建多模型预测</div>
        </div>
      </div>

      <div className="platform-overview-grid">
        <div className="platform-surface-card">
          <div className="platform-surface-card-head">
            <h4>推荐工作流</h4>
            <span className="muted">按顺序完成即可上手</span>
          </div>
          <div className="platform-workflow platform-workflow-timeline">
            {WORKFLOW.map((w, i) => (
              <div key={w.step} className="platform-workflow-step">
                <div className="platform-workflow-rail">
                  <div className="platform-workflow-num">{w.step}</div>
                  {i < WORKFLOW.length - 1 && <div className="platform-workflow-line" />}
                </div>
                <div className="platform-workflow-body">
                  <div className="platform-workflow-title">{w.title}</div>
                  <div className="platform-workflow-desc">{w.desc}</div>
                  <div className="platform-workflow-actions">
                    {w.action === 'config' && <Link className="btn sm" to="/config">前往设置</Link>}
                    {w.tab && (
                      <button type="button" className="btn sm primary" onClick={() => onNavigate(w.tab)}>
                        进入
                      </button>
                    )}
                    {w.link && <Link className="btn sm" to={w.link}>预测任务 ↗</Link>}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {!!datasets.length && (
          <div className="platform-surface-card">
            <div className="platform-surface-card-head">
              <h4>数据集快捷入口</h4>
              <button type="button" className="btn sm btn-ghost" onClick={() => onNavigate('datasets')}>查看全部</button>
            </div>
            <div className="platform-quick-grid">
              {datasets.slice(0, 8).map((ds) => (
                <button
                  key={ds.id}
                  type="button"
                  className="platform-quick-card"
                  onClick={() => onNavigate('datasets')}
                >
                  <span className={`platform-quick-tag platform-quick-tag-${ds.source_type}`}>
                    {ds.source_type === 'snapshot' ? '快照' : '底库'}
                  </span>
                  <span className="platform-quick-name">{ds.name}</span>
                  <span className="platform-quick-meta">#{ds.source_id}</span>
                </button>
              ))}
              {datasets.length > 8 && (
                <button type="button" className="platform-quick-card platform-quick-card-more" onClick={() => onNavigate('datasets')}>
                  +{datasets.length - 8} 更多
                </button>
              )}
            </div>
          </div>
        )}

        {!datasets.length && (
          <div className="platform-surface-card platform-empty-state">
            <div className="platform-empty-state-icon" aria-hidden="true" />
            <h4>还没有数据集</h4>
            <p>通过「发现导入」从 Magic-Fox URL 批量添加，或在「数据集」页手动配置。</p>
            <div className="platform-empty-actions">
              <button type="button" className="btn sm primary" onClick={() => onNavigate('discover')}>发现导入</button>
              <button type="button" className="btn sm" onClick={() => onNavigate('datasets')}>手动添加</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
