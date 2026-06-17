import { useCallback, useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import FlowPipelineStrip from '../components/flows/FlowPipelineStrip';
import FlowRunsHistoryPanel from '../components/flows/FlowRunsHistoryPanel';
import FlowsSceneShell from '../components/flows/FlowsSceneShell';
import { useHumanGates } from '../hooks/useHumanGates';
import { usePolling } from '../hooks/usePolling';
import { flowRunPath } from '../lib/flowsRun';

const TABS = [
  { id: 'browse', label: '流水线' },
  { id: 'history', label: '执行历史' },
];

function isUserComposeFlow(flowId) {
  const fid = String(flowId || '');
  if (!fid || fid === 'flow_draft') return false;
  if (fid.startsWith('custom_')) return false;
  if (/unit_test|_test_/i.test(fid)) return false;
  return fid.startsWith('flow_');
}

export default function FlowsCatalogPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const tabParam = searchParams.get('tab');
  const tab = tabParam === 'history' ? 'history' : 'browse';
  const [flows, setFlows] = useState([]);
  const [savedFlows, setSavedFlows] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingSaved, setLoadingSaved] = useState(false);
  const { count: gateCount, reload: reloadGates } = useHumanGates({
    pollInterval: 8000,
    enabled: true,
  });

  const loadTasks = useCallback(async () => {
    try {
      const list = await api.flowList();
      if (list.success) setFlows(list.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  const loadSavedFlows = useCallback(async () => {
    setLoadingSaved(true);
    try {
      const r = await api.forgeComposeFlows();
      if (r.success) {
        setSavedFlows((r.data || []).filter((f) => isUserComposeFlow(f.flow_id)));
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setLoadingSaved(false);
    }
  }, []);

  useEffect(() => {
    if (tab === 'browse') {
      loadTasks();
      loadSavedFlows();
    }
  }, [loadTasks, loadSavedFlows, tab]);

  usePolling(reloadGates, { interval: 8000, immediate: false, enabled: gateCount > 0 });

  const setTab = (id) => {
    const next = new URLSearchParams(searchParams);
    if (id === 'history') next.set('tab', 'history');
    else {
      next.delete('tab');
      next.delete('status');
    }
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

  const onRunCatalogFlow = async (flow) => {
    if (flow.engine === 'workflow' && flow.id?.startsWith('flow_')) {
      navigate(`/flows/compose?flow=${encodeURIComponent(flow.id)}`);
      return;
    }
    if (!flow.runnable) {
      navigate(`/flows/tasks/${encodeURIComponent(flow.id)}`);
      return;
    }
    setBusy(true);
    try {
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

  const resumeFlow = async (item) => {
    const runKey = item?.meta?.run_key
      || (item?.href?.includes('/flows/runs/') ? decodeURIComponent(item.href.split('/flows/runs/')[1] || '') : '');
    if (!runKey) return;
    setBusy(true);
    try {
      const r = await api.orchestrationResume({ run_key: runKey });
      if (r.success) {
        toast('已继续执行', 'success');
        await reloadGates();
      } else {
        toast(r.error || 'Resume 失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const catalogFlows = flows.filter((f) => f.valid !== false && f.engine !== 'workflow');

  return (
    <FlowsSceneShell layout="wide">
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">流水线目录</h1>
          <p className="flows-page-desc">
            {tab === 'history'
              ? '全部运行的执行记录、状态筛选与待人工处理。'
              : '管理已保存的自定义流水线，或使用 Catalog 官方模板。'}
          </p>
        </div>
        <div className="flows-page-actions">
          {tab === 'browse' && (
            <>
              <Link to="/flows/compose" className="btn btn-sm btn-primary">新建流水线</Link>
              <button type="button" className="btn btn-sm" disabled={busy} onClick={onSync}>同步 Catalog</button>
            </>
          )}
          {tab === 'history' && gateCount > 0 && (
            <Link to="/flows?tab=history&status=waiting_human" className="btn btn-sm btn-primary">
              {gateCount} 待人工
            </Link>
          )}
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
            {t.id === 'history' && gateCount > 0 && (
              <span className="flows-tab-badge">{gateCount}</span>
            )}
          </button>
        ))}
      </div>

      {tab === 'browse' && gateCount > 0 && (
        <section className="flows-gates-banner platform-surface-card">
          <span className="flows-gates-banner-text">
            {gateCount} 个流水线运行待人工处理
          </span>
          <Link to="/flows?tab=history&status=waiting_human" className="btn btn-sm btn-primary">
            前往执行历史
          </Link>
        </section>
      )}

      {tab === 'browse' && (
        <>
          <section className="flows-section flows-mine-section">
            <div className="flows-section-head">
              <h2 className="flows-section-title">
                我的流水线
                {savedFlows.length > 0 && (
                  <span className="flows-section-count">{savedFlows.length}</span>
                )}
              </h2>
            </div>
            {loadingSaved && !savedFlows.length ? (
              <div className="empty-state">加载中…</div>
            ) : !savedFlows.length ? (
              <div className="panel empty-state flows-mine-empty">
                尚未保存流水线。
                {' '}
                <Link to="/flows/compose">前往组合编排创建</Link>
              </div>
            ) : (
              <table className="flows-table flows-mine-table">
                <thead>
                  <tr>
                    <th>流水线</th>
                    <th>步骤</th>
                    <th>定时</th>
                    <th>更新</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {savedFlows.map((f) => (
                    <tr key={f.flow_id}>
                      <td className="flows-task-name-cell">
                        <div className="flows-run-name">{f.name || f.flow_id}</div>
                        <div className="flows-run-sub">{f.flow_id}</div>
                      </td>
                      <td>{f.step_count ?? '—'} 步</td>
                      <td>
                        {f.schedule_enabled ? (
                          <span className="flows-mine-schedule-on">已启用</span>
                        ) : (
                          <span className="muted">未启用</span>
                        )}
                        {f.next_run_at && (
                          <div className="flows-run-sub">下次 {f.next_run_at}</div>
                        )}
                      </td>
                      <td className="flows-table-mono">{f.updated || '—'}</td>
                      <td className="flows-task-actions-cell">
                        <Link
                          to={`/flows/compose?flow=${encodeURIComponent(f.flow_id)}`}
                          className="btn btn-sm btn-primary"
                        >
                          打开
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="flows-section flows-catalog-section">
            <div className="flows-section-head">
              <h2 className="flows-section-title">
                Catalog 模板
                {catalogFlows.length > 0 && (
                  <span className="flows-section-count">{catalogFlows.length}</span>
                )}
              </h2>
            </div>
            {!catalogFlows.length ? (
              <div className="panel empty-state">暂无 Catalog 流水线；请点击「同步 Catalog」</div>
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
                  {catalogFlows.map((f) => (
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
                            onClick={() => onRunCatalogFlow(f)}
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
              <Link to="/flows/tasks/welcome_demo">welcome_demo</Link>
            </p>
          </section>
        </>
      )}

      {tab === 'history' && (
        <FlowRunsHistoryPanel onResume={resumeFlow} />
      )}
    </FlowsSceneShell>
  );
}
