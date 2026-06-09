import { useCallback, useEffect, useState } from 'react';
import { api, toast } from '../api/client';

const STATUS_LABEL = {
  done: '完成',
  waiting_human: '等待人工',
  failed: '失败',
  skipped: '跳过',
};

function StepTimeline({ steps }) {
  if (!steps?.length) return null;
  return (
    <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.8 }}>
      {steps.map((s) => (
        <li key={s.step_id}>
          <strong>{s.step_id}</strong>
          <span style={{ color: 'var(--muted)', marginLeft: 8 }}>{s.tool}</span>
          <span style={{
            marginLeft: 8,
            fontSize: 12,
            color: s.status === 'done' ? '#059669' : s.status === 'waiting_human' ? '#b45309' : '#b91c1c',
          }}
          >
            {STATUS_LABEL[s.status] || s.status}
          </span>
        </li>
      ))}
    </ol>
  );
}

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

  return (
    <div className="panel active" style={{ padding: 20, maxWidth: 960 }}>
      <h2 style={{ margin: '0 0 8px' }}>编排演示</h2>
      <p style={{ margin: '0 0 20px', color: 'var(--muted)' }}>
        迷你 Flow 体验 Windmill 式编排：模拟查询 → 打包 → 人工卡点 → 通知。无需数据库。
      </p>

      {info && (
        <div className="card" style={{ padding: 16, marginBottom: 16 }}>
          <div style={{ fontWeight: 600 }}>{info.name}</div>
          <pre style={{ whiteSpace: 'pre-wrap', fontSize: 13, color: 'var(--muted)', margin: '8px 0 0' }}>
            {info.description}
          </pre>
          <div style={{ marginTop: 12, fontSize: 13 }}>
            步骤：
            {(info.nodes || []).map((n) => n.id).join(' → ')}
          </div>
        </div>
      )}

      <div className="card" style={{ padding: 16, marginBottom: 16 }}>
        <label style={{ display: 'block', marginBottom: 8 }}>
          操作人（params.reviewer）
          <input
            type="text"
            className="input"
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            style={{ display: 'block', width: '100%', marginTop: 4 }}
          />
        </label>
        <label style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
          <input type="checkbox" checked={autoResume} onChange={(e) => setAutoResume(e.target.checked)} />
          自动跳过人工卡点（等同 CLI --auto-resume）
        </label>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button type="button" className="btn primary" disabled={busy} onClick={() => onRun(false)}>
            运行演示流
          </button>
          {pendingRunId && !autoResume && (
            <button type="button" className="btn" disabled={busy} onClick={() => onRun(true)}>
              继续运行（人工确认）
            </button>
          )}
        </div>
      </div>

      {result && (
        <div className="card" style={{ padding: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 12 }}>
            <strong>运行结果</strong>
            <span style={{ fontSize: 13, color: 'var(--muted)' }}>
              run_id: {result.run_id}
              {' · '}
              status: {result.status}
            </span>
          </div>
          <StepTimeline steps={result.steps} />
          <pre style={{
            marginTop: 16, fontSize: 12, overflow: 'auto', maxHeight: 360,
            background: 'var(--bg-subtle)', padding: 12, borderRadius: 8,
          }}
          >
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}

      <div style={{ marginTop: 24, fontSize: 13, color: 'var(--muted)' }}>
        CLI 等价命令：
        <pre style={{ background: 'var(--bg-subtle)', padding: 12, borderRadius: 8, marginTop: 8 }}>
          {`./scripts/iisp flow run welcome_demo --reviewer ${reviewer}${autoResume ? ' --auto-resume' : ''}`}
        </pre>
      </div>
    </div>
  );
}
