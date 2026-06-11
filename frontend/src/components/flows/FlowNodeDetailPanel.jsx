import { stepMeta } from '../../lib/workflowCatalog';
import { formatDateTime, formatDuration } from '../../lib/time';
import { statusLabel, WORKFLOW_STEP_STATUS_MAP } from '../ui/statusMap';
import FlowReadableFields from './FlowReadableFields';

export default function FlowNodeDetailPanel({ node, mode = 'design', flowReadable = null }) {
  if (!node) {
    return (
      <div className="flows-node-detail flows-node-detail--empty">
        <p className="flows-muted">点击流程节点，查看入参、出参与运行结果</p>
      </div>
    );
  }

  const meta = stepMeta(node.tool_id || node.kind);
  const tool = node.tool;
  const readable = node.readable || {};
  const title = readable.step_title || tool?.label || meta.label;
  const summary = readable.step_summary || tool?.description || meta.desc;

  return (
    <div className="flows-node-detail">
      <header className="flows-node-detail-head">
        <div>
          <h3>{title}</h3>
          <div className="flows-node-detail-sub">
            步骤
            {' '}
            <code>{node.id}</code>
            {node.tool_id && node.tool_id !== node.id && (
              <>
                {' · 工具 '}
                <code>{node.tool_id}</code>
              </>
            )}
          </div>
        </div>
        {node.status && (
          <span className={`flows-node-detail-status flows-node-detail-status--${node.status}`}>
            {statusLabel(node.status, WORKFLOW_STEP_STATUS_MAP)}
          </span>
        )}
      </header>

      {summary && <p className="flows-node-detail-desc">{summary}</p>}

      {readable.upstream_note && (
        <p className="flows-node-upstream-note">
          <span className="flows-node-upstream-label">上游</span>
          {readable.upstream_note}
        </p>
      )}

      <section className="flows-node-detail-section">
        <h4>入参</h4>
        <FlowReadableFields
          fields={readable.inputs}
          mode={mode}
          variant="in"
        />
      </section>

      <section className="flows-node-detail-section">
        <h4>出参</h4>
        <FlowReadableFields
          fields={readable.outputs}
          mode={mode}
          variant="out"
        />
      </section>

      {mode === 'run' && <RunDetailSections node={node} />}

      {mode === 'run' && node.error && (
        <section className="flows-node-detail-section">
          <h4>错误</h4>
          <p className="flows-step-error">{node.error}</p>
        </section>
      )}

      {node.node_kind === 'branch' && readable.branch_condition_human && (
        <section className="flows-node-detail-section flows-node-detail-section--highlight">
          <h4>分支说明</h4>
          <p className="flows-node-detail-desc">{readable.branch_condition_human}</p>
        </section>
      )}

      {flowReadable?.summary && !readable.step_title && (
        <section className="flows-node-detail-section flows-node-detail-section--muted">
          <h4>流程概要</h4>
          <p className="flows-node-detail-desc">{flowReadable.summary}</p>
        </section>
      )}
    </div>
  );
}

function RunDetailSections({ node }) {
  const rd = node.run_detail || {};
  const started = formatDateTime(rd.started_at || node.started_at);
  const ended = formatDateTime(rd.ended_at || node.ended_at);
  const duration = formatDuration(node.duration_seconds, { compact: false });
  const metaRows = [
    ['状态', statusLabel(rd.status || node.status, WORKFLOW_STEP_STATUS_MAP)],
    ['工具返回', rd.tool_status],
    ['HTTP', rd.http_code],
    ['开始', started],
    ['结束', ended],
    ['耗时', duration],
  ].filter(([, v]) => v != null && v !== '');

  const artifacts = Array.isArray(rd.artifacts) ? rd.artifacts : [];
  const hasRaw = rd.raw != null;
  const hasAnything = metaRows.length > 0 || rd.reason || artifacts.length || hasRaw;

  if (!hasAnything && !node.status) return null;

  return (
    <section className="flows-node-detail-section flows-node-run">
      <h4>执行过程与结果</h4>
      {metaRows.length > 0 && (
        <dl className="flows-node-run-meta">
          {metaRows.map(([k, v]) => (
            <div key={k} className="flows-node-run-meta-row">
              <dt>{k}</dt>
              <dd>{String(v)}</dd>
            </div>
          ))}
        </dl>
      )}
      {rd.reason && (
        <p className="flows-node-run-reason">
          <span className="flows-node-upstream-label">说明</span>
          {rd.reason}
        </p>
      )}
      {artifacts.length > 0 && (
        <div className="flows-node-run-artifacts">
          <span className="flows-node-run-label">产物</span>
          <ul>
            {artifacts.map((a, i) => (
              <li key={typeof a === 'string' ? a : i}>
                {typeof a === 'string' ? a : JSON.stringify(a)}
              </li>
            ))}
          </ul>
        </div>
      )}
      {hasRaw && (
        <details className="flows-node-run-raw">
          <summary>原始返回</summary>
          <pre>{typeof rd.raw === 'string' ? rd.raw : JSON.stringify(rd.raw, null, 2)}</pre>
        </details>
      )}
      {!hasAnything && (
        <p className="flows-muted">该步骤尚未执行或无返回数据</p>
      )}
    </section>
  );
}

