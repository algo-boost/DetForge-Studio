import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import FlowPipelineStrip from '../components/flows/FlowPipelineStrip';
import HumanGatesPanel from '../components/flows/HumanGatesPanel';
import SceneHubNav from '../components/SceneHubNav';
import StatusPill from '../components/ui/StatusPill';
import { useHumanGates } from '../hooks/useHumanGates';
import { usePolling } from '../hooks/usePolling';
import { flowRunPath } from '../lib/flowsRun';

const TABS = [
  { id: 'tasks', label: '编排任务' },
  { id: 'history', label: '执行历史' },
];

export default function FlowsCatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const tab = searchParams.get('tab') === 'history' ? 'history' : 'tasks';
  const [flows, setFlows] = useState([]);
  const [runs, setRuns] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(false);
  const { items: humanGates, count: gateCount, reload: reloadGates } = useHumanGates();

  const loadTasks = useCallback(async () => {
    try {
      const list = await api.flowList();
      if (list.success) setFlows(list.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.flowRunsList('?limit=80');
      if (r.success) setRuns(r.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTasks();
    if (tab === 'history') loadHistory();
  }, [loadTasks, loadHistory, tab]);

  usePolling(loadHistory, { interval: 8000, immediate: false, enabled: tab === 'history' });

  const setTab = (id) => {
    const next = new URLSearchParams(searchParams);
    if (id === 'history') next.set('tab', 'history');
    else next.delete('tab');
    setSearchParams(next);
  };

  const onSync = async () => {
    setBusy(true);
    try {
      const r = await api.catalogSync();
      if (r.success) {
        toast('Catalog 已同步', 'success');
        await loadTasks();
      } else {
        toast(r.data?.error || '同步失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onRunFlow = async (flow) => {
    if (!flow.runnable) {
      navigate(`/flows/tasks/${encodeURIComponent(flow.id)}`);
      return;
    }
    setBusy(true);
    try {
      if (flow.engine === 'kestra') {
        if (!flow.kestra_enabled) {
          toast('Kestra 未启用', 'error');
          return;
        }
        const defaults = {};
        for (const [k, spec] of Object.entries(flow.params_schema || {})) {
          if (spec?.default != null) defaults[k] = spec.default;
        }
        const r = await api.flowKestraExecute({
          flow_id: flow.id,
          namespace: flow.namespace,
          inputs: defaults,
        });
        const data = r.data || {};
        if (r.success && data.run_key) {
          toast('已启动', 'success');
          await reloadGates();
          navigate(flowRunPath(data.run_key));
          return;
        }
        toast(r.error || data.error || '运行失败', 'error');
        return;
      }
      const r = await api.flowRun({ flow_id: flow.id, params: {}, auto_resume: false });
      const runId = r.data?.run_id || r.run_id;
      if (runId) {
        toast('已启动', 'success');
        navigate(flowRunPath(`demo:${runId}`));
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const resumeKestra = async (item) => {
    const executionId = item?.meta?.execution_id;
    if (!executionId) return;
    setBusy(true);
    try {
      const r = await api.orchestrationResume({ execution_id: executionId });
      if (r.success) {
        toast('已继续执行', 'success');
        await reloadGates();
        if (tab === 'history') await loadHistory();
      } else {
        toast(r.error || 'Resume 失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const kestraFlows = flows.filter((f) => f.engine === 'kestra' && f.valid !== false);

  return (
    <div className="panel active flows-page flows-page--wide">
      <SceneHubNav variant="flows" />
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">编排</h1>
          <p className="flows-page-desc">编排任务、流程图与执行历史</p>
        </div>
        <div className="flows-page-actions">
          <button type="button" className="btn btn-sm" disabled={busy} onClick={onSync}>同步 Catalog</button>
        </div>
      </header>

      <div className="flows-status-tabs">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            className={`flows-status-tab${tab === t.id ? ' is-active' : ''}`}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {gateCount > 0 && tab === 'tasks' && (
        <section className="flows-gates-section">
          <h2 className="flows-section-title">
            待人工处理
            <span className="flows-gate-badge">{gateCount}</span>
          </h2>
          <HumanGatesPanel items={humanGates} onResumeKestra={resumeKestra} compact />
        </section>
      )}

      {tab === 'tasks' && (
        <>
          {!kestraFlows.length ? (
            <div className="panel empty-state">暂无编排任务，请先同步 Catalog 并启动 Kestra</div>
          ) : (
            <table className="flows-table flows-task-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>流程图</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {kestraFlows.map((f) => (
                  <tr key={f.id}>
                    <td className="flows-task-name-cell">
                      <div className="flows-run-name">{f.label || f.id}</div>
                      <div className="flows-run-sub">{f.id}</div>
                      {f.description && (
                        <div className="flows-task-desc">{String(f.description).trim().split('\n')[0]}</div>
                      )}
                    </td>
                    <td className="flows-task-pipeline-cell">
                      <FlowPipelineStrip nodes={f.nodes} flowId={f.id} />
                    </td>
                    <td className="flows-task-actions-cell">
                      <Link to={`/flows/tasks/${encodeURIComponent(f.id)}`} className="btn btn-sm">
                        详情
                      </Link>
                      {f.runnable && (
                        <button
                          type="button"
                          className="btn btn-sm btn-primary"
                          disabled={busy}
                          onClick={() => onRunFlow(f)}
                        >
                          运行
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <p className="flows-footnote">
            推荐入门：
            {' '}
            <Link to="/flows/tasks/closed_loop_demo_smoke">closed_loop_demo_smoke</Link>
            （样本模式，无需数据库）
          </p>
        </>
      )}

      {tab === 'history' && (
        <>
          {loading && !runs.length ? (
            <div className="empty-state">加载中…</div>
          ) : !runs.length ? (
            <div className="empty-state">暂无执行记录</div>
          ) : (
            <table className="flows-table flows-runs-table">
              <thead>
                <tr>
                  <th>任务</th>
                  <th>运行 ID</th>
                  <th>状态</th>
                  <th>时间</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {runs.map((run) => (
                  <tr
                    key={run.run_key}
                    className={run.status === 'waiting_human' ? 'flows-row-waiting' : ''}
                  >
                    <td>
                      {run.flow_id ? (
                        <Link to={`/flows/tasks/${encodeURIComponent(run.flow_id)}`}>
                          {run.name || run.flow_id}
                        </Link>
                      ) : (
                        run.name || '—'
                      )}
                    </td>
                    <td className="flows-table-mono">{run.run_id}</td>
                    <td><StatusPill status={run.status} /></td>
                    <td>{run.created_at || '—'}</td>
                    <td>
                      <Link to={flowRunPath(run.run_key)} className="btn btn-sm">详情</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}
