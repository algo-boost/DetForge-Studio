import { Link } from 'react-router-dom';

const SCENES = [
  {
    id: 'daily_ng',
    title: '每日 NG 捞',
    flow: '查询 → 外部筛图 → 交接训练',
    primary: { label: '去查询', to: '/' },
    secondary: { label: '查看批次', filter: 'daily_ng' },
  },
  {
    id: 'replay_eval',
    title: '历史回跑',
    flow: '选预测作业 → 筛 NG/FP/FN → 交接',
    primary: { label: '开始回跑', action: 'replay' },
  },
  {
    id: 'customer_qc',
    title: '人工质检',
    flow: 'SN 对齐 → 分类 → 交接训练',
    primary: { label: '去人工质检', to: '/manual-qc' },
    secondary: { label: '生成交接包', action: 'qc_handoff' },
  },
];

export default function SceneLoopHub({ qcSummary, onReplay, onQcHandoff, onFilterIntent, busy }) {
  return (
    <section className="loop-hub" data-testid="scene-loop-hub">
      <p className="loop-hub-lead muted">
        三条业务线共用同一套交接格式（COCO + images → training_inbox）。选一个场景开始。
      </p>
      <div className="loop-hub-grid">
        {SCENES.map((s) => (
          <article key={s.id} className={`loop-card loop-card-${s.id}`}>
            <h3>{s.title}</h3>
            <p className="loop-card-flow">{s.flow}</p>
            {s.id === 'customer_qc' && qcSummary && (
              <p className="loop-card-stat muted">
                待交接 {qcSummary.pending || 0} 条
                {(qcSummary.handoff_ready || 0) > 0 && ` · 已就绪 ${qcSummary.handoff_ready}`}
              </p>
            )}
            <div className="loop-card-actions">
              {s.primary.to ? (
                <Link to={s.primary.to} className="btn btn-primary">{s.primary.label}</Link>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={busy}
                  onClick={() => (s.primary.action === 'replay' ? onReplay() : null)}
                  data-testid={s.id === 'replay_eval' ? 'hub-start-replay' : undefined}
                >
                  {s.primary.label}
                </button>
              )}
              {s.secondary?.to && (
                <Link to={s.secondary.to} className="btn btn-ghost">{s.secondary.label}</Link>
              )}
              {s.secondary?.filter && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => onFilterIntent?.(s.secondary.filter)}
                >
                  {s.secondary.label}
                </button>
              )}
              {s.secondary?.action === 'qc_handoff' && (
                <button
                  type="button"
                  className="btn btn-ghost"
                  disabled={busy || !(qcSummary?.pending)}
                  onClick={onQcHandoff}
                  data-testid="hub-qc-handoff"
                >
                  {s.secondary.label}
                </button>
              )}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
