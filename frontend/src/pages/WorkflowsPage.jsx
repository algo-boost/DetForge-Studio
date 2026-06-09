import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import WorkflowDagEditor from '../components/forge/WorkflowDagEditor';
import WorkflowFlowCanvas from '../components/forge/WorkflowFlowCanvas';
import WorkflowParamsForm from '../components/forge/WorkflowParamsForm';
import WorkflowPipelineViz from '../components/forge/WorkflowPipelineViz';
import { graphFromLinearSteps } from '../lib/workflowGraph';
import { defaultParamsFromSchema } from '../lib/workflowCatalog';

const RUN_STATUS = {
  pending: '排队',
  running: '运行中',
  waiting_human: '待上传 COCO',
  done: '完成',
  failed: '失败',
  canceled: '已取消',
  paused: '暂停',
};

function StatusPill({ status, map }) {
  const label = map[status] || status || '—';
  return <span className={`wf-pill wf-pill-${status || 'default'}`}>{label}</span>;
}

export default function WorkflowsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [tab, setTab] = useState('compose');
  const [templates, setTemplates] = useState([]);
  const [runs, setRuns] = useState([]);
  const [schedules, setSchedules] = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedRunId, setSelectedRunId] = useState(null);
  const [runDetail, setRunDetail] = useState(null);
  const [selectedStepId, setSelectedStepId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [launchTpl, setLaunchTpl] = useState('');
  const [launchParams, setLaunchParams] = useState({});
  const [agentDraft, setAgentDraft] = useState('');
  const [agentResult, setAgentResult] = useState(null);

  const selectedTemplate = useMemo(
    () => templates.find((t) => t.id === launchTpl),
    [templates, launchTpl],
  );

  const loadTemplates = useCallback(async () => {
    try {
      const r = await api.forgeWorkflowTemplates();
      if (r.success) setTemplates(r.data || []);
    } catch (e) { /* ignore */ }
  }, []);

  const loadRuns = useCallback(async () => {
    try {
      const r = await api.forgeWorkflowRuns('?limit=80');
      if (r.success) setRuns(r.data || []);
    } catch (e) { /* ignore */ }
  }, []);

  const loadSchedules = useCallback(async () => {
    try {
      const r = await api.forgeWorkflowSchedules();
      if (r.success) setSchedules(r.data || []);
    } catch (e) { /* ignore */ }
  }, []);

  const loadNotifications = useCallback(async () => {
    try {
      const r = await api.forgeWorkflowNotifications('?limit=40');
      if (r.success) setNotifications(r.data || []);
    } catch (e) { /* ignore */ }
  }, []);

  const loadDetail = useCallback(async (id) => {
    if (!id) { setRunDetail(null); return; }
    try {
      const r = await api.forgeWorkflowRun(id);
      if (r.success) setRunDetail(r);
    } catch (e) { toast(e.message, 'error'); }
  }, []);

  useEffect(() => {
    loadTemplates();
    loadRuns();
    loadSchedules();
    loadNotifications();
    api.forgeModels(true).then((r) => {
      if (r.success) setModels(r.data || []);
    }).catch(() => {});
  }, [loadTemplates, loadRuns, loadSchedules, loadNotifications]);

  useEffect(() => {
    const runParam = searchParams.get('run');
    if (runParam) {
      const id = parseInt(runParam, 10);
      if (id) {
        setSelectedRunId(id);
        setTab('runs');
        loadDetail(id);
      }
    }
  }, [searchParams, loadDetail]);

  useEffect(() => {
    if (!selectedRunId) return undefined;
    const t = setInterval(() => loadDetail(selectedRunId), 4000);
    return () => clearInterval(t);
  }, [selectedRunId, loadDetail]);

  const waitingRuns = useMemo(
    () => runs.filter((r) => r.status === 'waiting_human'),
    [runs],
  );

  const selectRun = (id) => {
    setSelectedRunId(id);
    setSelectedStepId(null);
    setSearchParams(id ? { run: String(id) } : {});
    loadDetail(id);
  };

  const startRun = async (body) => {
    setBusy(true);
    try {
      const r = await api.forgeWorkflowRunCreate(body);
      if (r.success) {
        toast(`已启动编排 #${r.data.id}`);
        loadRuns();
        setTab('runs');
        selectRun(r.data.id);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const launchFromTemplate = () => {
    if (!launchTpl) { toast('请选择模板', 'error'); return; }
    startRun({ template_id: launchTpl, params: launchParams });
  };

  const resumeRun = async (id) => {
    setBusy(true);
    try {
      const r = await api.forgeWorkflowRunResume(id);
      if (r.success) {
        toast('已继续流程');
        loadRuns();
        loadDetail(id);
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const toggleSchedule = async (sched) => {
    setBusy(true);
    try {
      await api.forgeWorkflowScheduleUpdate(sched.id, { enabled: sched.enabled ? 0 : 1 });
      loadSchedules();
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const triggerSchedule = async (id) => {
    setBusy(true);
    try {
      const r = await api.forgeWorkflowScheduleTrigger(id);
      if (r.success) {
        toast(r.skipped ? '已跳过（互斥或缺少 model_id）' : `已触发运行 #${r.data?.id}`);
        loadRuns();
        loadSchedules();
      }
    } catch (e) { toast(e.message, 'error'); }
    finally { setBusy(false); }
  };

  const pickTemplate = (tpl) => {
    setLaunchTpl(tpl.id);
    const schema = tpl.definition?.params_schema || {};
    const defaults = defaultParamsFromSchema(schema);
    if (tpl.id === 'weekly_predict_eval' && models[0]) {
      defaults.model_id = models[0].id;
    }
    setLaunchParams(defaults);
    setTab('compose');
  };

  const gateStep = runDetail?.steps?.find((s) => s.status === 'waiting_human');
  const batchId = gateStep?.child_batch_id || gateStep?.human_action?.batch_id;

  const runGraph = useMemo(() => {
    if (!runDetail) return null;
    if (runDetail.graph?.nodes?.length) return runDetail.graph;
    const steps = runDetail.template?.definition?.steps || [];
    if (!steps.length) return null;
    return graphFromLinearSteps(steps);
  }, [runDetail]);

  const stepStatusMap = useMemo(() => {
    const m = {};
    (runDetail?.steps || []).forEach((s) => { m[s.step_id] = s.status; });
    return m;
  }, [runDetail]);

  const vizSteps = useMemo(() => {
    if (!runDetail) return [];
    const defMap = Object.fromEntries(
      (runDetail.template?.definition?.steps || []).map((s) => [s.id, s]),
    );
    return (runDetail.steps || []).map((s) => ({
      id: s.step_id,
      kind: s.kind || defMap[s.step_id]?.kind,
      status: s.status,
    }));
  }, [runDetail]);

  const activeStep = runDetail?.steps?.find((s) => s.step_id === selectedStepId)
    || runDetail?.steps?.find((s) => s.status === 'running' || s.status === 'waiting_human')
    || null;

  return (
    <div className="panel active wf-page">
      <header className="wf-header">
        <div>
          <div className="topbar-title">工作流编排</div>
          <p className="wf-header-desc">
            LangFlow 风格编排：左侧组件库、画布拖线、贝塞尔分支、边中点插入步骤
          </p>
        </div>
        {waitingRuns.length > 0 && (
          <div className="wf-waiting-banner">
            {waitingRuns.length} 个流程待上传 COCO
          </div>
        )}
      </header>

      <div className="wf-tabs">
        {[
          ['compose', '流程设计器'],
          ['agent', '工作流助手'],
          ['runs', '运行记录'],
          ['schedules', '定时'],
          ['templates', '模板库'],
          ['notifications', '通知'],
        ].map(([t, label]) => (
          <button
            key={t}
            type="button"
            className={`wf-tab${tab === t ? ' is-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === 'compose' && (
        <div className="wf-compose-panel">
          <WorkflowDagEditor
            models={models}
            busy={busy}
            onLaunch={({ definition, params, name }) => startRun({ definition, params, name })}
          />

          <section className="wf-quick-launch">
            <h4>或从内置模板快速启动</h4>
            <div className="wf-quick-row">
              <select value={launchTpl} onChange={(e) => {
                const tpl = templates.find((t) => t.id === e.target.value);
                setLaunchTpl(e.target.value);
                if (tpl) {
                  const d = defaultParamsFromSchema(tpl.definition?.params_schema);
                  if (tpl.id === 'weekly_predict_eval' && models[0]) d.model_id = models[0].id;
                  setLaunchParams(d);
                }
              }}
              >
                <option value="">选择内置模板…</option>
                {templates.filter((t) => t.builtin).map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
            </div>
            {selectedTemplate && (
              <>
                <WorkflowPipelineViz
                  steps={(selectedTemplate.definition?.steps || []).map((s) => ({
                    id: s.id,
                    kind: s.kind,
                  }))}
                  compact
                />
                <WorkflowParamsForm
                  schema={selectedTemplate.definition?.params_schema || {}}
                  value={launchParams}
                  onChange={setLaunchParams}
                  models={models}
                />
                <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={launchFromTemplate}>
                  启动模板
                </button>
              </>
            )}
          </section>
        </div>
      )}

      {tab === 'agent' && (
        <section className="wf-compose-panel" style={{ padding: 16 }}>
          <h4>工作流助手（Agent 配置通道）</h4>
          <p style={{ fontSize: 13, color: 'var(--muted)' }}>
            粘贴含 <code>```yaml</code> 代码块的 Pipeline 草稿，校验通过后导入为工作流模板。
          </p>
          <textarea
            rows={14}
            style={{ width: '100%', fontFamily: 'monospace', fontSize: 12 }}
            placeholder={'```yaml\nid: my_flow\nnodes:\n  - id: query\n    tool: query\n    params:\n      strategy_id: daily_trawl\n```'}
            value={agentDraft}
            onChange={(e) => setAgentDraft(e.target.value)}
          />
          <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
            <button
              type="button"
              className="btn btn-sm btn-primary"
              disabled={busy || !agentDraft.trim()}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api.workflowAgentCompile({ text: agentDraft });
                  setAgentResult(r.data || null);
                  if (r.success) toast('YAML 校验通过');
                  else toast((r.data?.errors || [r.data?.error]).join?.('; ') || '校验失败', 'error');
                } catch (e) { toast(e.message, 'error'); }
                finally { setBusy(false); }
              }}
            >
              校验 YAML
            </button>
            <button
              type="button"
              className="btn btn-sm"
              disabled={busy || !agentResult?.success}
              onClick={async () => {
                setBusy(true);
                try {
                  const r = await api.workflowImport({
                    pipeline: agentResult.pipeline,
                    definition: agentResult.definition,
                  });
                  if (r.success) {
                    toast(`已导入模板: ${r.data?.id}`);
                    loadTemplates();
                    setTab('templates');
                  }
                } catch (e) { toast(e.message, 'error'); }
                finally { setBusy(false); }
              }}
            >
              导入为模板
            </button>
          </div>
          {agentResult ? (
            <pre style={{ marginTop: 12, fontSize: 11, background: 'var(--bg-subtle)', padding: 12, borderRadius: 8, overflow: 'auto' }}>
              {JSON.stringify(agentResult, null, 2)}
            </pre>
          ) : null}
        </section>
      )}

      {tab === 'runs' && (
        <div className="wf-layout">
          <section className="wf-list-panel">
            <table className="wf-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>名称</th>
                  <th>状态</th>
                  <th>创建</th>
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => (
                  <tr
                    key={r.id}
                    className={selectedRunId === r.id ? 'is-selected' : ''}
                    onClick={() => selectRun(r.id)}
                  >
                    <td>{r.id}</td>
                    <td>{r.name || '—'}</td>
                    <td><StatusPill status={r.status} map={RUN_STATUS} /></td>
                    <td>{r.created_at || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <section className="wf-detail-panel">
            {!runDetail ? (
              <p className="wf-muted">选择运行查看流程图与步骤详情</p>
            ) : (
              <>
                <div className="wf-detail-head">
                  <h3>#{runDetail.run.id} {runDetail.run.name}</h3>
                  <StatusPill status={runDetail.run.status} map={RUN_STATUS} />
                </div>

                {runGraph ? (
                  <div className="wf-flow-run-canvas">
                    <WorkflowFlowCanvas
                      graph={runGraph}
                      stepStatus={stepStatusMap}
                      selectedId={selectedStepId}
                      onSelectNode={setSelectedStepId}
                      readOnly
                    />
                  </div>
                ) : (
                  <WorkflowPipelineViz
                    steps={vizSteps}
                    onSelectStep={(s) => setSelectedStepId(s.id)}
                  />
                )}

                {runDetail.run.status === 'waiting_human' && (
                  <div className="wf-human-card">
                    <p>{gateStep?.human_action?.instructions || '请上传筛选后的 COCO JSON'}</p>
                    <div className="wf-human-actions">
                      {batchId && (
                        <Link to={`/curation?batch_id=${batchId}`} className="btn btn-sm">
                          前往筛选归档上传
                        </Link>
                      )}
                      <button type="button" className="btn btn-sm btn-primary" disabled={busy} onClick={() => resumeRun(runDetail.run.id)}>
                        已上传，继续流程
                      </button>
                    </div>
                  </div>
                )}

                {activeStep && (
                  <div className="wf-step-detail">
                    <h4>
                      步骤 {activeStep.step_id}
                      <StatusPill status={activeStep.status} map={{
                        pending: '待执行', running: '执行中', done: '完成',
                        failed: '失败', skipped: '已跳过', waiting_human: '待人工',
                      }}
                      />
                    </h4>
                    {activeStep.output && (
                      <pre className="wf-step-output">{JSON.stringify(activeStep.output, null, 2)}</pre>
                    )}
                    {activeStep.error && <p className="wf-step-error">{activeStep.error}</p>}
                  </div>
                )}
              </>
            )}
          </section>
        </div>
      )}

      {tab === 'schedules' && (
        <div className="wf-schedules">
          <p className="wf-muted">
            每周预测评测调度需在 params 中配置 model_id；通知在设置 workflow_notify 中配置。
          </p>
          <table className="wf-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>名称</th>
                <th>模板</th>
                <th>Cron</th>
                <th>下次</th>
                <th>启用</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {schedules.map((s) => (
                <tr key={s.id}>
                  <td>{s.id}</td>
                  <td>{s.name}</td>
                  <td><code>{s.template_id}</code></td>
                  <td><code>{s.cron_expr}</code></td>
                  <td>{s.next_run_at || '—'}</td>
                  <td>{s.enabled ? '是' : '否'}</td>
                  <td>
                    <button type="button" className="btn btn-sm" disabled={busy} onClick={() => toggleSchedule(s)}>
                      {s.enabled ? '禁用' : '启用'}
                    </button>
                    <button type="button" className="btn btn-sm" disabled={busy} onClick={() => triggerSchedule(s.id)}>
                      立即触发
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {tab === 'templates' && (
        <div className="wf-templates">
          {templates.map((t) => (
            <article key={t.id} className="wf-template-card">
              <h4>{t.name}</h4>
              <p>{t.description}</p>
              {t.definition?.graph?.nodes?.length ? (
                <div className="wf-flow-run-canvas wf-flow-run-canvas-sm">
                  <WorkflowFlowCanvas graph={t.definition.graph} readOnly />
                </div>
              ) : (
                <WorkflowPipelineViz
                  steps={(t.definition?.steps || []).map((s) => ({ id: s.id, kind: s.kind }))}
                  compact
                />
              )}
              <button type="button" className="btn btn-sm" onClick={() => pickTemplate(t)}>
                在编排器中使用
              </button>
            </article>
          ))}
        </div>
      )}

      {tab === 'notifications' && (
        <table className="wf-table wf-notif-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>渠道</th>
              <th>事件</th>
              <th>标题</th>
              <th>运行</th>
            </tr>
          </thead>
          <tbody>
            {notifications.map((n) => (
              <tr key={n.id}>
                <td>{n.created_at}</td>
                <td>{n.channel}</td>
                <td>{n.event}</td>
                <td>{n.title}</td>
                <td>
                  {n.run_id ? (
                    <button type="button" className="btn-link" onClick={() => { setTab('runs'); selectRun(n.run_id); }}>
                      #{n.run_id}
                    </button>
                  ) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
