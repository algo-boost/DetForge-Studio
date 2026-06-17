import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import FlowGraphPanel from '../components/flows/FlowGraphPanel';
import FlowParamsForm from '../components/flows/FlowParamsForm';
import FlowAssistantPanel from '../components/flows/FlowAssistantPanel';
import FlowsSceneShell from '../components/flows/FlowsSceneShell';
import StatusPill from '../components/ui/StatusPill';
import { defaultParamsFromSchema } from '../lib/workflowCatalog';
import { flowRunPath } from '../lib/flowsRun';

export default function FlowTaskDetailPage() {
  const { flowId } = useParams();
  const [searchParams] = useSearchParams();
  const initialNodeId = searchParams.get('node') || null;
  const navigate = useNavigate();
  const [flow, setFlow] = useState(null);
  const [graph, setGraph] = useState(null);
  const [loading, setLoading] = useState(true);
  const [runs, setRuns] = useState([]);
  const [params, setParams] = useState({});
  const [models, setModels] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!flowId) return;
    setLoading(true);
    try {
      const [listR, runsR] = await Promise.all([
        api.flowList(),
        api.flowRunsList(`?flow_id=${encodeURIComponent(flowId)}&limit=30`),
      ]);
      let found = null;
      if (listR.success) {
        found = (listR.data || []).find((f) => f.id === flowId) || null;
        if (found?.params_schema) {
          setParams((prev) => (Object.keys(prev).length ? prev : defaultParamsFromSchema(found.params_schema)));
        }
      }
      if (!found && String(flowId).startsWith('custom_')) {
        const graphR = await api.flowPipelineGraph(flowId);
        if (graphR.success && graphR.data) {
          setGraph(graphR.data);
          found = {
            id: flowId,
            label: flowId,
            engine: 'workflow',
            description: '组合编排自动保存的模板；请从「组合编排」页配置并运行。',
            runnable: false,
            params_schema: {},
          };
        }
      }
      setFlow(found);
      if (runsR.success) setRuns(runsR.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
      setFlow(null);
    } finally {
      setLoading(false);
    }
  }, [flowId]);

  useEffect(() => { load(); }, [load]);

  // Flow 含 model 类型参数时加载注册模型，供模型下拉选择
  const needsModels = useMemo(
    () => Object.values(flow?.params_schema || {}).some((s) => s?.type === 'model'),
    [flow],
  );
  useEffect(() => {
    if (!needsModels) return;
    api.forgeModels(true).then((r) => {
      const list = (r.data || r.models || []).map((m) => ({
        id: m.id,
        name: m.name || m.model_name || `#${m.id}`,
      }));
      setModels(list);
    }).catch(() => setModels([]));
  }, [needsModels]);

  const onRun = async () => {
    if (!flow?.runnable) return;
    setBusy(true);
    try {
      const r = await api.flowRun({ flow_id: flow.id, params, auto_resume: false });
      const runId = r.data?.run_id || r.run_id;
      if (runId) {
        toast('已启动', 'success');
        navigate(flowRunPath(`demo:${runId}`));
        return;
      }
      toast(r.data?.reason || '运行失败', 'error');
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const title = useMemo(() => flow?.label || flow?.id || flowId, [flow, flowId]);
  const isComposeTemplate = flow?.engine === 'workflow' || String(flowId).startsWith('custom_');

  if (!flowId) {
    return (
      <div className="panel active flows-page">
        <p className="flows-muted">缺少任务 ID</p>
      </div>
    );
  }

  return (
    <FlowsSceneShell layout="wide">
      <header className="flows-page-header">
        <div>
          <h1 className="flows-page-title">{title}</h1>
          <p className="flows-page-desc">
            <code>{flowId}</code>
            {flow?.engine && (
              <>
                {' · '}
            {flow?.engine === 'workflow' ? '组合编排' : 'Legacy'}
              </>
            )}
          </p>
          {flow?.description && (
            <p className="flows-page-intro">{flow.description.split('\n')[0]}</p>
          )}
        </div>
        <Link to={isComposeTemplate ? '/flows/compose' : '/flows'} className="btn btn-sm">
          {isComposeTemplate ? '前往组合编排' : '返回任务列表'}
        </Link>
      </header>

      {loading ? (
        <div className="empty-state">加载中…</div>
      ) : !flow ? (
        <div className="empty-state">
          <p>未找到任务 <code>{flowId}</code></p>
          <Link to="/flows/compose" className="btn btn-sm" style={{ marginTop: 12 }}>打开组合编排</Link>
        </div>
      ) : (
        <>
          {isComposeTemplate && (
            <section className="flows-section flows-human-card">
              <p>此为组合编排运行自动保存的模板，不可在此页直接运行。请前往组合编排重新配置并执行。</p>
              <Link to="/flows/compose" className="btn btn-sm btn-primary">打开组合编排</Link>
            </section>
          )}

          <section className="flows-section flows-task-workspace">
            <h2 className="flows-section-title">流程与运行</h2>
            <p className="flows-section-hint">
              {isComposeTemplate
                ? '只读流程图；运行请使用组合编排页。'
                : '左侧流程图与节点详情；右侧填写运行参数并立即执行。修改拓扑请编辑 Git YAML。'}
            </p>
            <div className={`flows-task-workspace-grid${flow.runnable ? '' : ' flows-task-workspace-grid--graph-only'}`}>
              <div className="flows-task-workspace-main flows-detail-panel">
                <FlowGraphPanel
                  flowId={graph ? undefined : flowId}
                  graph={graph}
                  mode="design"
                  initialSelectedId={initialNodeId}
                />
              </div>
              {flow.runnable && (
                <aside className="flows-task-workspace-aside flows-detail-panel">
                  <h3 className="flows-aside-title">运行参数</h3>
                  <FlowParamsForm
                    schema={flow.params_schema || {}}
                    value={params}
                    onChange={setParams}
                    models={models}
                  />
                  <button type="button" className="btn btn-sm btn-primary flows-run-btn" disabled={busy} onClick={onRun}>
                    立即运行
                  </button>
                </aside>
              )}
            </div>
          </section>

          {!isComposeTemplate && (
          <section className="flows-section flows-task-assistant-section">
            <h2 className="flows-section-title">编排助手</h2>
            <p className="flows-section-hint">描述需求生成 YAML 草稿，或基于当前 Flow 微调后校验预览。</p>
            <div className="flows-detail-panel flows-assistant-wrap">
              <FlowAssistantPanel flowId={flowId} compact />
            </div>
          </section>
          )}

          <section className="flows-section">
            <h2 className="flows-section-title">执行历史</h2>
            {!runs.length ? (
              <div className="panel empty-state">该任务尚无执行记录</div>
            ) : (
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
                  {runs.map((run) => (
                    <tr key={run.run_key}>
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
          </section>
        </>
      )}
    </FlowsSceneShell>
  );
}
