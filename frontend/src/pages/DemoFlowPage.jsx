import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import StepTimeline from '../components/flows/StepTimeline';
import { flowRunPath } from '../lib/flowsRun';

export default function DemoFlowPage() {
  const [info, setInfo] = useState(null);
  const [reviewer, setReviewer] = useState('demo-user');
  const [autoResume, setAutoResume] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [pendingRunId, setPendingRunId] = useState(null);

  const load = useCallback(async () => {
    try {
      const r = await api.flowDemoInfo();
      if (r.success) setInfo(r.data);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const onRun = async (resume = false) => {
    setBusy(true);
    if (!resume) setResult(null);
    try {
      const body = {
        flow_id: 'welcome_demo',
        params: { reviewer },
        auto_resume: autoResume,
      };
      if (resume && pendingRunId) {
        body.resume_run_id = pendingRunId;
        body.approved_by = reviewer;
      }
      const r = await api.flowRun(body);
      setResult(r.data || r);
      if (r.status === 'waiting_human') {
        setPendingRunId(r.data?.run_id);
        toast('流程在人工卡点暂停，点击「继续运行」', 'info');
      } else if (r.success || r.status === 'done') {
        setPendingRunId(null);
        toast('演示流运行完成', 'success');
      } else {
        toast(r.data?.reason || '运行失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const runId = result?.run_id || pendingRunId;

  return (
    <div className="panel active flows-page">
      <SceneHubNav variant="flows" />
      <h2 className="flows-page-title">编排演示</h2>
      <p className="flows-page-desc">
        迷你 Flow：demo-query → demo-pack → gate-human → demo-notify。无需数据库。
      </p>

      {info && (
        <div className="panel flows-demo-card">
          <div className="flows-card-title">{info.name}</div>
          <pre className="flows-demo-desc">{info.description}</pre>
          <div className="flows-card-meta">
            步骤：
            {(info.nodes || []).map((n) => n.id).join(' → ')}
          </div>
        </div>
      )}

      <div className="panel flows-demo-card">
        <label className="flows-demo-label">
          操作人（params.reviewer）
          <input
            type="text"
            className="input"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
          />
        </label>
        <label className="flows-demo-check">
          <input type="checkbox" checked={autoResume} onChange={(e) => setAutoResume(e.target.checked)} />
          自动跳过人工卡点（等同 CLI --auto-resume）
        </label>
        <div className="flows-demo-actions">
          <button type="button" className="btn btn-primary" disabled={busy} onClick={() => onRun(false)}>
            运行演示流
          </button>
          {pendingRunId && !autoResume && (
            <button type="button" className="btn" disabled={busy} onClick={() => onRun(true)}>
              继续运行（人工确认）
            </button>
          )}
          {runId && (
            <Link to={flowRunPath(`demo:${runId}`)} className="btn btn-sm">
              打开运行详情
            </Link>
          )}
        </div>
      </div>

      {result && (
        <div className="panel flows-demo-card">
          <div className="flows-demo-result-head">
            <strong>运行结果</strong>
            <span className="flows-muted">
              run_id: {result.run_id}
              {' · '}
              status: {result.status}
            </span>
          </div>
          <StepTimeline steps={result.steps} />
        </div>
      )}

      <div className="flows-footnote">
        CLI：
        <pre className="flows-cli-pre">
          {`./scripts/iisp flow run welcome_demo --reviewer ${reviewer}${autoResume ? ' --auto-resume' : ''}`}
        </pre>
      </div>
    </div>
  );
}
