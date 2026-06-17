import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import ComposeModulePanel from '../components/compose/ComposeModulePanel';
import ComposeGlobalRunPanel, { envDictToRows } from '../components/compose/ComposeGlobalRunPanel';
import ComposeSchedulePanel from '../components/compose/ComposeSchedulePanel';
import FlowsSceneShell from '../components/flows/FlowsSceneShell';
import WorkflowPipelineViz from '../components/forge/WorkflowPipelineViz';
import { flowRunPath } from '../lib/flowsRun';
import {
  COMPOSE_MODULE_GROUPS,
  composeStepHints,
  defaultComposePipelineState,
  getComposeModule,
  modulesForGroup,
  newComposeStep,
  normalizeFlowId,
  reindexComposeSteps,
} from '../lib/composeModules';
import { envRowsToDict } from '../lib/envVars';
import { defaultRunParamsDefaults } from '../lib/runEnvSpec';
import { validateComposeStep } from '../lib/composeModuleParams';

export default function ComposePipelinePage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [flowId, setFlowId] = useState(() => normalizeFlowId(searchParams.get('flow') || 'flow_draft'));
  const [name, setName] = useState('');
  const [steps, setSteps] = useState(() => defaultComposePipelineState(flowId));
  const [runParamsCore, setRunParamsCore] = useState(() => defaultRunParamsDefaults());
  const [extraEnvRows, setExtraEnvRows] = useState(() => envDictToRows({}));
  const [schedule, setSchedule] = useState(null);
  const [savedFlows, setSavedFlows] = useState([]);
  const [models, setModels] = useState([]);
  const [busy, setBusy] = useState(false);
  const [loadingFlow, setLoadingFlow] = useState(false);
  const [expandedStepUid, setExpandedStepUid] = useState(null);
  const [stepExpandMode, setStepExpandMode] = useState('single');
  const [asideOpen, setAsideOpen] = useState(true);

  const runParamsDefaults = useMemo(
    () => ({
      ...runParamsCore,
      env: envRowsToDict(extraEnvRows),
    }),
    [runParamsCore, extraEnvRows],
  );

  const loadSavedFlows = useCallback(() => {
    api.forgeComposeFlows().then((r) => {
      if (r.success) setSavedFlows(r.data || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.forgeModels(true).then((r) => {
      if (r.success) setModels(r.data || []);
    }).catch(() => {});
    loadSavedFlows();
  }, [loadSavedFlows]);

  const loadFlow = useCallback(async (id) => {
    const fid = normalizeFlowId(id);
    if (!fid || fid === 'flow_draft') {
      setFlowId('flow_draft');
      setSteps(defaultComposePipelineState('flow_draft'));
      setName('');
      setSchedule(null);
      setRunParamsCore(defaultRunParamsDefaults());
      setExtraEnvRows(envDictToRows({}));
      setExpandedStepUid(null);
      return;
    }
    setLoadingFlow(true);
    try {
      const r = await api.forgeComposeFlowGet(fid);
      if (!r.success || !r.data) throw new Error('流水线不存在');
      const flow = r.data;
      setFlowId(flow.flow_id);
      setName(flow.name || '');
      setSteps(flow.step_instances || defaultComposePipelineState(flow.flow_id));
      const defaults = flow.run_params_defaults || defaultRunParamsDefaults();
      setRunParamsCore({
        env_spec: defaults.env_spec,
      });
      setExtraEnvRows(envDictToRows(defaults.env || {}));
      setSchedule(flow.schedule || null);
      const first = (flow.step_instances || [])[0];
      setExpandedStepUid(first?.uid || null);
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      setLoadingFlow(false);
    }
  }, []);

  useEffect(() => {
    const q = searchParams.get('flow');
    if (q) loadFlow(q);
  }, [searchParams, loadFlow]);

  const vizSteps = useMemo(
    () => steps.map((s) => {
      const mod = getComposeModule(s.moduleId);
      return { id: s.uid, kind: mod?.kind || s.moduleId, label: mod?.label };
    }),
    [steps],
  );

  const setStepParams = useCallback((uid, next) => {
    setSteps((prev) => prev.map((s) => (s.uid === uid ? { ...s, params: next } : s)));
  }, []);

  const withReindex = useCallback((nextSteps) => reindexComposeSteps(flowId, nextSteps), [flowId]);

  const addModule = (moduleId) => {
    setSteps((prev) => {
      const next = withReindex([...prev, newComposeStep(moduleId, prev, flowId)]);
      const added = next[next.length - 1];
      if (added?.uid && stepExpandMode === 'single') setExpandedStepUid(added.uid);
      return next;
    });
  };

  const removeStep = (uid) => {
    setSteps((prev) => {
      if (prev.length <= 1) return prev;
      const next = withReindex(prev.filter((s) => s.uid !== uid));
      if (expandedStepUid === uid) {
        setExpandedStepUid(next[0]?.uid || null);
      }
      return next;
    });
  };

  const moveStep = (index, dir) => {
    setSteps((prev) => {
      const next = [...prev];
      const j = index + dir;
      if (j < 0 || j >= next.length) return prev;
      [next[index], next[j]] = [next[j], next[index]];
      return withReindex(next);
    });
  };

  useEffect(() => {
    setSteps((prev) => withReindex(prev));
  }, [flowId, withReindex]);

  useEffect(() => {
    if (!expandedStepUid && steps.length && stepExpandMode === 'single') {
      setExpandedStepUid(steps[0].uid);
    }
  }, [steps, expandedStepUid, stepExpandMode]);

  const isStepExpanded = useCallback((uid) => {
    if (stepExpandMode === 'all') return true;
    if (stepExpandMode === 'none') return false;
    return uid === expandedStepUid;
  }, [stepExpandMode, expandedStepUid]);

  const expandAllSteps = () => setStepExpandMode('all');
  const collapseAllSteps = () => {
    setStepExpandMode('none');
    setExpandedStepUid(null);
  };

  const onStepExpand = useCallback((uid) => {
    if (uid) {
      setStepExpandMode('single');
      setExpandedStepUid(uid);
    } else {
      setStepExpandMode('none');
      setExpandedStepUid(null);
    }
  }, []);

  const validate = () => {
    for (let i = 0; i < steps.length; i += 1) {
      const inst = steps[i];
      const mod = getComposeModule(inst.moduleId);
      if (!mod) continue;
      const hints = composeStepHints(steps, i);
      const err = validateComposeStep(inst.moduleId, inst.params, hints);
      if (err) {
        toast(`步骤 ${i + 1}「${mod.label}」：${err}`, 'error');
        return false;
      }
    }
    return true;
  };

  const onSave = async () => {
    const fid = normalizeFlowId(flowId);
    const indexed = reindexComposeSteps(fid, steps);
    setBusy(true);
    try {
      const r = await api.forgeComposeFlowSave({
        flow_id: fid,
        name: name.trim() || fid,
        step_instances: indexed,
        run_params_defaults: runParamsDefaults,
      });
      if (r.success) {
        setFlowId(r.data.flow_id);
        setSteps(r.data.step_instances || indexed);
        toast(`流水线已保存：${r.data.flow_id}`, 'success');
        loadSavedFlows();
        setSearchParams({ flow: r.data.flow_id }, { replace: true });
      }
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onRun = async () => {
    if (!validate()) return;
    setBusy(true);
    try {
      const fid = normalizeFlowId(flowId);
      const indexed = reindexComposeSteps(fid, steps);
      const runName = name.trim() || `组合编排 · ${new Date().toLocaleString('zh-CN')}`;
      const r = await api.forgeWorkflowRunCreate({
        flow_id: fid,
        name: runName,
        step_instances: indexed,
        params: runParamsDefaults,
      });
      if (r.success) {
        toast(`已启动编排 #${r.data.id}（${fid}）`);
        navigate(flowRunPath(`workflow:${r.data.id}`));
      }
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      setBusy(false);
    }
  };

  const onSelectSavedFlow = (e) => {
    const id = e.target.value;
    if (!id) {
      setSearchParams({}, { replace: true });
      loadFlow('flow_draft');
      return;
    }
    setSearchParams({ flow: id }, { replace: true });
  };

  const savedFlowValue = searchParams.get('flow') || '';

  return (
    <FlowsSceneShell layout="compose" className="compose-pipeline-page">
      <header className="compose-page-header">
        <div className="compose-page-header-main">
          <h1 className="flows-page-title">组合编排</h1>
          <p className="flows-page-desc">
            从模块库添加步骤并配置参数，保存后可重复运行或定时触发。
          </p>
        </div>
        <div className="compose-toolbar">
          <button
            type="button"
            className={`btn btn-sm btn-ghost compose-aside-toggle${asideOpen ? ' is-active' : ''}`}
            onClick={() => setAsideOpen((v) => !v)}
            title={asideOpen ? '隐藏运行设定侧栏' : '显示运行设定侧栏'}
          >
            {asideOpen ? '隐藏运行设定' : '运行设定'}
          </button>
          <label className="compose-toolbar-field compose-toolbar-field--load">
            <span>已保存</span>
            <select
              className="form-select"
              value={savedFlowValue}
              onChange={onSelectSavedFlow}
              disabled={loadingFlow}
            >
              <option value="">新建草稿</option>
              {savedFlows.map((f) => (
                <option key={f.flow_id} value={f.flow_id}>
                  {f.name || f.flow_id}（{f.step_count} 步{f.schedule_enabled ? ' · 定时' : ''}）
                </option>
              ))}
            </select>
          </label>
          <label className="compose-toolbar-field">
            <span>流水线 ID</span>
            <input
              className="form-input"
              type="text"
              placeholder="flow_daily_fp"
              value={flowId}
              onChange={(e) => setFlowId(normalizeFlowId(e.target.value))}
              spellCheck={false}
            />
          </label>
          <label className="compose-toolbar-field">
            <span>显示名称</span>
            <input
              className="form-input"
              type="text"
              placeholder="可选"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <div className="compose-toolbar-actions">
            <Link to="/flows" className="btn btn-sm btn-ghost">目录</Link>
            <button type="button" className="btn btn-secondary" disabled={busy} onClick={onSave}>
              {busy ? '处理中…' : '保存'}
            </button>
            <button type="button" className="btn btn-primary" disabled={busy || loadingFlow} onClick={onRun}>
              {busy ? '启动中…' : '运行一次'}
            </button>
          </div>
          {loadingFlow && <span className="muted compose-toolbar-status">加载中…</span>}
        </div>
      </header>

      <div className={`compose-layout${asideOpen ? '' : ' is-aside-collapsed'}`}>
        <aside className="compose-layout-sidebar" aria-label="模块库">
          <section className="compose-module-palette platform-surface-card">
            <h2 className="compose-palette-title">模块库</h2>
            <p className="muted compose-palette-hint">
              点击添加模块；上游 task_id / job_id / batch_id 按步骤类型自动承接。
            </p>
            <div className="compose-palette-groups">
              {COMPOSE_MODULE_GROUPS.map((group) => (
                <div key={group.id} className="compose-palette-group">
                  <span className="compose-palette-group-label">{group.label}</span>
                  <div className="compose-palette-chips">
                    {modulesForGroup(group.id).map((mod) => (
                      <button
                        key={mod.moduleId}
                        type="button"
                        className="btn btn-sm compose-palette-chip"
                        onClick={() => addModule(mod.moduleId)}
                      >
                        + {mod.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </aside>

        <main className="compose-layout-main">
          <div className="compose-viz-strip">
            <WorkflowPipelineViz steps={vizSteps} compact />
          </div>
          <div className="compose-steps-toolbar">
            <span className="compose-steps-toolbar-label">
              步骤链
              <span className="muted"> · {steps.length} 步</span>
            </span>
            <div className="compose-steps-toolbar-actions">
              <button type="button" className="btn btn-sm btn-ghost" onClick={expandAllSteps}>全部展开</button>
              <button type="button" className="btn btn-sm btn-ghost" onClick={collapseAllSteps}>全部收起</button>
            </div>
          </div>
          <div className="compose-steps-stack">
            {steps.map((inst, idx) => {
              const mod = getComposeModule(inst.moduleId);
              if (!mod) return null;
              return (
                <ComposeModulePanel
                  key={inst.uid}
                  step={{ uid: inst.uid, kind: mod.kind, label: mod.label }}
                  moduleId={inst.moduleId}
                  stepIndex={idx}
                  totalSteps={steps.length}
                  paramsSchema={mod.paramsSchema}
                  bindHints={composeStepHints(steps, idx)}
                  value={inst.params}
                  onChange={(next) => setStepParams(inst.uid, next)}
                  onMoveUp={() => moveStep(idx, -1)}
                  onMoveDown={() => moveStep(idx, 1)}
                  onRemove={() => removeStep(inst.uid)}
                  models={models}
                  expanded={isStepExpanded(inst.uid)}
                  onExpand={onStepExpand}
                />
              );
            })}
          </div>
        </main>

        <aside className="compose-layout-aside" aria-label="运行与调度">
          <ComposeGlobalRunPanel
            flowId={flowId}
            runParamsDefaults={runParamsDefaults}
            onRunParamsDefaultsChange={(next) => setRunParamsCore({
              env_spec: next.env_spec,
            })}
            extraEnvRows={extraEnvRows}
            onExtraEnvRowsChange={setExtraEnvRows}
          />
          <ComposeSchedulePanel
            flowId={flowId}
            name={name}
            steps={steps}
            runParamsDefaults={runParamsDefaults}
            validate={validate}
            busy={busy}
            onBusyChange={setBusy}
            initialSchedule={schedule}
            onScheduleChange={setSchedule}
          />
        </aside>
      </div>
    </FlowsSceneShell>
  );
}
