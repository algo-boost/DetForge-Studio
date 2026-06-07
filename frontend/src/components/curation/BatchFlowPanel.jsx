import { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { buildQueryResultsPath } from '../../lib/queryResultsNav';
import { api } from '../../api/client';
import {
  DISPOSITION_LABEL,
  FLOW_STEPS,
  INTENT_LABEL,
  STATUS_LABEL,
  flowStepIndex,
  nextBatchAction,
} from '../../lib/curationFlow';

function FlowProgress({ status }) {
  const idx = flowStepIndex(status);
  return (
    <div className="flow-progress" data-testid="curation-flow-progress">
      {FLOW_STEPS.map((s, i) => (
        <div
          key={s.key}
          className={`flow-progress-step${i < idx ? ' is-done' : ''}${i === idx ? ' is-current' : ''}`}
        >
          <span className="flow-progress-dot">{i < idx ? '✓' : ''}</span>
          <span className="flow-progress-label">{s.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function BatchFlowPanel({
  batch,
  items,
  busy,
  onExport,
  onImportFile,
  onArchiveHandoff,
  onHandoff,
  onHandoffDone,
  onDeleteRequest,
}) {
  const importRef = useRef(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showItems, setShowItems] = useState(false);

  const action = nextBatchAction(batch?.status);
  const st = batch?.status || '';
  const stepDone = {
    export: ['exported', 'imported', 'archived', 'handoff_ready', 'handoff_done', 'closed'].includes(st),
    import: ['imported', 'archived', 'handoff_ready', 'handoff_done', 'closed'].includes(st),
  };

  const onPrimary = () => {
    if (!action) return;
    switch (action.key) {
      case 'export': onExport(); break;
      case 'import': importRef.current?.click(); break;
      case 'archive_handoff': onArchiveHandoff(); break;
      case 'handoff': onHandoff('both'); break;
      case 'done': onHandoffDone(); break;
      default: break;
    }
  };

  const predictJobId = batch?.strategy_id?.startsWith('replay_job_')
    ? batch.strategy_id.replace('replay_job_', '')
    : null;

  return (
    <div className="batch-flow" data-testid="batch-flow-panel">
      <div className="batch-flow-head">
        <div>
          <h2>{batch.batch_code}</h2>
          <p className="muted batch-flow-meta">
            {INTENT_LABEL[batch.intent_type] || batch.intent_type}
            {' · '}
            {STATUS_LABEL[st] || st}
            {' · '}
            留 {batch.keep_count} / 剔 {batch.reject_count}
          </p>
        </div>
        <div className="batch-flow-links">
          {predictJobId && (
            <Link to={`/?predict_job=${predictJobId}`} className="btn btn-ghost">预测作业</Link>
          )}
          <Link to={buildQueryResultsPath(batch.source_task_id)} className="btn btn-ghost">来源结果</Link>
          <button
            type="button"
            className="btn btn-ghost btn-danger-text"
            disabled={busy}
            onClick={() => onDeleteRequest?.(batch)}
            data-testid="curation-delete-batch"
          >
            删除批次
          </button>
        </div>
      </div>

      <FlowProgress status={st} />

      {action && (
        <div className="batch-flow-next">
          <p className="batch-flow-hint">{action.hint}</p>
          {batch.export_dir && action.key === 'import' && (
            <p className="batch-flow-path-short muted" data-testid="curation-export-path">{batch.export_dir}</p>
          )}
          <input
            ref={importRef}
            type="file"
            accept=".json,application/json"
            hidden
            onChange={(e) => { onImportFile(e.target.files?.[0]); e.target.value = ''; }}
          />
          <button
            type="button"
            className="btn btn-primary batch-flow-cta"
            disabled={busy}
            onClick={onPrimary}
            data-testid="curation-next-step"
          >
            {action.label}
          </button>
        </div>
      )}

      {!action && (
        <p className="loop-hub-lead muted">本批次已闭环。</p>
      )}

      <details className="batch-flow-advanced" open={showAdvanced} onToggle={(e) => setShowAdvanced(e.target.open)}>
        <summary>分步操作 / 下载</summary>
        <div className="batch-flow-advanced-body">
          <div className="cur-step-actions">
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={onExport}>
              {stepDone.export ? '重新出站' : '仅出站'}
            </button>
            {batch.export_dir && (
              <a className="btn btn-ghost" href={api.forgeCurationDownloadUrl(batch.id)} download>
                下载 ZIP
              </a>
            )}
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy || !stepDone.export}
              onClick={() => importRef.current?.click()}
              data-testid="curation-import-coco"
            >
              上传 COCO
            </button>
            <button type="button" className="btn btn-ghost" disabled={busy} onClick={() => onHandoff('need_label')}>
              仅 to_label 交接
            </button>
          </div>
          {(batch.export_dir || batch.archive_dir || batch.handoff_dir) && (
            <ul className="batch-flow-paths muted">
              {batch.export_dir && <li>出站：{batch.export_dir}</li>}
              {batch.archive_dir && <li>归档：{batch.archive_dir}</li>}
              {batch.handoff_dir && <li>交接：{batch.handoff_dir}</li>}
            </ul>
          )}
        </div>
      </details>

      {items.length > 0 && (
        <details className="batch-flow-advanced" open={showItems} onToggle={(e) => setShowItems(e.target.open)}>
          <summary>条目预览（{items.length}）</summary>
          <table className="cur-items-table">
            <thead>
              <tr>
                <th>图片</th>
                <th>SN</th>
                <th>标签</th>
              </tr>
            </thead>
            <tbody>
              {items.slice(0, 50).map((it) => (
                <tr key={it.id}>
                  <td className="cur-td-name">{it.img_name}</td>
                  <td>{it.product_no || '—'}</td>
                  <td>{DISPOSITION_LABEL[it.disposition] || it.disposition || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
    </div>
  );
}
