import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import FlowGraphPanel from '../components/flows/FlowGraphPanel';
import FlowRunInputsSummary from '../components/flows/FlowRunInputsSummary';
import StatusPill from '../components/ui/StatusPill';
import { usePolling } from '../hooks/usePolling';
import { flowRunPath, kestraStudioPath } from '../lib/flowsRun';

export default function FlowRunDetailPage() {
  const { runKey: encodedKey } = useParams();
  const runKey = decodeURIComponent(encodedKey || '');
  const navigate = useNavigate();
  const [detail, setDetail] = useState(null);
  const [flowMeta, setFlowMeta] = useState(null);
  const [relatedRuns, setRelatedRuns] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!runKey) return;
    try {
      const r = await api.flowRunGet(runKey);
      if (r.success) {
        setDetail(r.data);
        const fid = r.data?.flow_id;
        if (fid) {
          const [listR, runsR] = await Promise.all([
            api.flowList(),
            api.flowRunsList(`?flow_id=${encodeURIComponent(fid)}&limit=15`),
          ]);
          if (listR.success) {
            setFlowMeta((listR.data || []).find((f) => f.id === fid) || null);
          }
          if (runsR.success) setRelatedRuns(runsR.data || []);
        }
      } else {
        toast(r.error || '加载失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, [runKey]);

  useEffect(() => { load(); }, [load]);

  usePolling(load, {
    interval: 4000,
    immediate: false,
    enabled: Boolean(detail) && ['running', 'waiting_human', 'pending'].includes(detail?.status),
  });

  const onResume = async () => {
    setBusy(true);
    try {
      const r = await api.flowRunResume(runKey, { approved_by: 'web-user' });
      if (r.success) {
        toast('已继续执行', 'success');
        await load();
        if (r.data?.data?.run_id && detail?.source === 'demo') {
          const newKey = `demo:${r.data.data.run_id}`;
          if (newKey !== runKey) navigate(flowRunPath(newKey), { replace: true });
        }
      } else {
        toast(r.error || 'Resume 失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  if (!runKey) {
    return (
      <div className="panel active flows-page">
        <p className="flows-muted">缺少 run_key</p>
      </div>
    );
  }

  const isWaiting = detail?.status === 'waiting_human';
  const gateInstructions = detail?.gate_step?.human_action?.instructions
    || (detail?.source === 'demo' ? '演示人工卡点：点击「继续运行」' : null);

  return (
    <div className="panel active flows-page flows-page--wide">
      <SceneHubNav variant="flows" />
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">执行详情</h1>
          <p className="flows-page-desc">
            {detail?.flow_id && (
              <>
                <Link to={`/flows/tasks/${encodeURIComponent(detail.flow_id)}`}>{detail.flow_id}</Link>
                {' · '}
              </>
            )}
            <code>{runKey}</code>
            {detail?.status && (
              <>
                {' · '}
                <StatusPill status={detail.status} />
              </>
            )}
          </p>
        </div>
        <Link to="/flows?tab=history" className="btn btn-sm">执行历史</Link>
      </header>

      {!detail ? (
        <div className="panel empty-state">加载中…</div>
      ) : (
        <>
          {isWaiting && (
            <section className="flows-human-card">
              <p>{gateInstructions || '需要人工处理后才能继续'}</p>
              <div className="flows-human-actions">
                {detail.batch_id && (
                  <Link to={`/curation?batch_id=${detail.batch_id}`} className="btn btn-sm">
                    前往筛选归档
                  </Link>
                )}
                {detail.kestra_url && (
                  <>
                    <Link to={kestraStudioPath(detail.kestra_url)} className="btn btn-sm">
                      Kestra 编排器
                    </Link>
                    <a href={detail.kestra_url} className="btn btn-sm" target="_blank" rel="noreferrer">
                      新窗口
                    </a>
                  </>
                )}
                <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={onResume}>
                  继续运行
                </button>
              </div>
            </section>
          )}

          {(detail.graph?.nodes?.length > 0 || detail.flow_id) && (
            <section className="flows-section flows-run-detail-section">
              <div className="flows-run-detail-head">
                <div>
                  <h2 className="flows-section-title">流程与步骤</h2>
                  <p className="flows-section-hint">左侧流程图、右侧节点详情（含本次实际入参/出参）；点击节点切换。</p>
                </div>
                {detail.flow_id && (
                  <Link to={`/flows/tasks/${encodeURIComponent(detail.flow_id)}`} className="btn btn-sm">
                    任务详情
                  </Link>
                )}
              </div>

              {detail.inputs && Object.keys(detail.inputs).length > 0 && (
                <div className="flows-run-inputs-block flows-detail-panel">
                  <h3 className="flows-run-inputs-title">本次运行参数</h3>
                  <FlowRunInputsSummary
                    inputs={detail.inputs}
                    schema={flowMeta?.params_schema || {}}
                  />
                </div>
              )}

              <div className="flows-detail-panel flows-run-graph-panel">
                <FlowGraphPanel
                  flowId={detail.flow_id}
                  graph={detail.graph}
                  mode="run"
                />
              </div>
            </section>
          )}

          {relatedRuns.length > 0 && (
            <section className="flows-section">
              <h2 className="flows-section-title">同任务执行历史</h2>
              <table className="flows-table flows-runs-table">
                <thead>
                  <tr>
                    <th>运行 ID</th>
                    <th>状态</th>
                    <th>时间</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {relatedRuns.map((run) => (
                    <tr key={run.run_key} className={run.run_key === runKey ? 'flows-row-current' : ''}>
                      <td className="flows-table-mono">{run.run_id}</td>
                      <td><StatusPill status={run.status} /></td>
                      <td>{run.created_at || '—'}</td>
                      <td>
                        {run.run_key === runKey ? (
                          <span className="flows-muted">当前</span>
                        ) : (
                          <Link to={flowRunPath(run.run_key)} className="btn btn-sm">查看</Link>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}

          {detail.notifications?.length > 0 && (
            <section className="flows-section">
              <h2 className="flows-section-title">通知</h2>
              <ul className="panel flows-legacy-list">
                {detail.notifications.map((n) => (
                  <li key={n.id} className="flows-legacy-item">
                    <div className="flows-legacy-name">{n.title || n.event}</div>
                    <div className="flows-legacy-meta">{n.created_at} · {n.channel}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <details className="flows-raw-details">
            <summary>原始 JSON</summary>
            <pre className="flows-yaml-pre">{JSON.stringify(detail, null, 2)}</pre>
          </details>
        </>
      )}
    </div>
  );
}
