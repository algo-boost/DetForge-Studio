import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import SceneHubNav from '../components/SceneHubNav';
import { api, toast } from '../api/client';
import { RulesBuilder } from '../components/RulesBuilder';
import { SqlEditor, PythonEditor } from '../components/Editors';
import { useRulesStudio } from '../hooks/useRulesStudio';
import { TemplateEditor } from '../components/TemplateEditor';
import { Modal } from '../components/Modal';
import { mergeFlowForSave, uiFilterMode } from '../lib/flowMerge';
import StrategyEnvSchemaEditor from '../components/StrategyEnvSchemaEditor';
import ProcessPipelineEditor from '../components/ProcessPipelineEditor';
import { defaultPipelineFromPresets } from '../lib/processPipeline';
import { envDefaultsFromSchema, parseEnvRandomSeed, parseEnvSampleSize } from '../lib/envVars';
import { TIME_ENV_FIELDS } from '../lib/strategyEnvSchema';
import { STRATEGY_DATA_SOURCES } from '../lib/strategyDataSource';
import { FILTER_MODE_LABEL, STRATEGY_EDITOR_TABS } from '../components/strategy/strategyUtils';
import QueryCompactHideEditor from '../components/strategy/QueryCompactHideEditor';
import { mergeCompactHideMap, serializeCompactHideForSave } from '../lib/queryCompactHide';

function StrategyEditorTabBar({ activeTab, onTabChange, hideRules }) {
  const tabs = STRATEGY_EDITOR_TABS.filter((t) => !(hideRules && t.id === 'rules'));
  return (
    <nav className="strategy-editor-tabs" aria-label="策略编辑区">
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          className={`strategy-editor-tab${activeTab === t.id ? ' is-active' : ''}`}
          onClick={() => onTabChange(t.id)}
        >
          <span className="strategy-editor-tab-label">{t.label}</span>
          <span className="strategy-editor-tab-desc">{t.desc}</span>
        </button>
      ))}
    </nav>
  );
}

function SidebarItem({ active, onClick, title, meta, badge }) {
  return (
    <button type="button" className={`strategy-list-item${active ? ' is-active' : ''}`} onClick={onClick}>
      <span className="strategy-list-main">
        <span className="strategy-list-title">{title}</span>
        {meta && <span className="strategy-list-meta">{meta}</span>}
      </span>
      {badge && <span className="strategy-list-badge">{badge}</span>}
    </button>
  );
}

function EmptyEditor() {
  return (
    <div className="strategy-empty-editor">
      <div className="strategy-empty-icon">
        <svg viewBox="0 0 48 48" fill="none" aria-hidden="true">
          <rect x="8" y="10" width="32" height="28" rx="3" stroke="currentColor" strokeWidth="2" />
          <path d="M16 20h16M16 26h10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
      </div>
      <h3>选择或新建策略</h3>
      <p>策略定义查询 SQL、筛选规则与 Python 后处理逻辑，可在查询页一键选用。</p>
      <div className="strategy-empty-actions">
        <Link to="/" className="btn btn-sm btn-ghost">前往查询页</Link>
      </div>
    </div>
  );
}

export default function AdminPage({ embedded = false }) {
  const [strategies, setStrategies] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [editing, setEditing] = useState(null);
  const [draft, setDraft] = useState(null);
  const [editorTab, setEditorTab] = useState('meta');
  const [sidebarFilter, setSidebarFilter] = useState('');
  const [deleteOpen, setDeleteOpen] = useState(false);
  const originalFlowRef = useRef(null);

  const markStale = () => {};
  const studio = useRulesStudio(markStale);

  const reload = async () => {
    const [s, t] = await Promise.all([api.getStrategies(), api.getTemplates()]);
    if (s.success) setStrategies(s.data || []);
    if (t.success) setTemplates(t.data || []);
  };

  useEffect(() => { reload(); }, []);

  const openStrategy = (s) => {
    setEditing({ type: 'strategy', id: s.id });
    const envSchema = (s.env_schema || []).map((row) => {
      const key = String(row?.key || '').toUpperCase();
      if (key === 'START_TIME' || key === 'END_TIME') return { ...row, type: 'datetime' };
      return row;
    });
    setDraft({
      ...s,
      env_schema: envSchema,
      filter_mode: uiFilterMode(s.filter_mode || 'flow'),
      query_ui_mode: s.query_ui_mode === 'compact' ? 'compact' : 'full',
      query_compact_hide: mergeCompactHideMap(s.query_compact_hide),
    });
    setEditorTab('meta');
    originalFlowRef.current = s.flow ? JSON.parse(JSON.stringify(s.flow)) : null;
    studio.setFlow(s.flow || { version: 2, nodes: [] }, {
      removeEmptyRows: s.remove_empty_rows,
      filterRulesCode: s.filter_rules_code,
    });
  };

  const newStrategy = () => {
    const id = `saved_${Date.now()}`;
    const s = {
      id, name: '新策略', category: 'custom', filter_mode: 'rules',
      sql_template: "SELECT * FROM product_detection_detail_result\nWHERE c_time BETWEEN '${START_TIME}' AND '${END_TIME}'",
      python_code: '',
      flow: { version: 2, nodes: [] },
      data_source: 'detail',
      env_schema: [...TIME_ENV_FIELDS],
      python_presets: ['observe', 'filter'],
      process_pipeline: defaultPipelineFromPresets(['observe', 'filter']),
    };
    setEditing({ type: 'strategy', id });
    setDraft(s);
    setEditorTab('meta');
    originalFlowRef.current = null;
    studio.setFlow(s.flow);
  };

  const newTemplate = () => {
    const id = `custom_${Date.now()}`;
    const t = {
      id, name: '新块模板', description: '', icon: 'code',
      params_schema: [], python_code: 'def filter(df, params):\n    return df',
    };
    setEditing({ type: 'template', id });
    setDraft(t);
    setEditorTab('meta');
  };

  const saveDraft = async () => {
    if (!draft) return;
    const mode = draft.filter_mode === 'flow' ? 'rules' : uiFilterMode(draft.filter_mode || 'rules');
    const envDefaults = envDefaultsFromSchema(draft.env_schema);
    const queryUiMode = draft.query_ui_mode === 'compact' ? 'compact' : 'full';
    const payload = {
      ...draft,
      filter_mode: mode,
      query_ui_mode: queryUiMode,
      query_compact_hide: queryUiMode === 'compact'
        ? serializeCompactHideForSave(draft.query_compact_hide)
        : undefined,
      sample_size: parseEnvSampleSize(envDefaults, draft.sample_size || 300),
      random_seed: parseEnvRandomSeed(envDefaults, draft.random_seed ?? 42),
      flow: mergeFlowForSave(originalFlowRef.current, studio.flow, studio.removeEmpty),
      remove_empty_rows: studio.removeEmpty,
      filter_rules_code: await studio.compile(),
    };
    try {
      const res = await api.saveStrategy(payload);
      if (!res.success) throw new Error(res.error);
      const fresh = await api.getStrategy(payload.id);
      if (fresh.success) openStrategy(fresh.data);
      toast('已保存');
      reload();
    } catch (e) { toast(e.message, 'error'); }
  };

  const duplicate = async () => {
    if (!draft) return;
    const copy = {
      ...draft,
      id: `saved_${Date.now()}`,
      name: `${draft.name} (副本)`,
      category: 'custom',
      is_preset: false,
      _preset: false,
      save_as_copy: true,
    };
    await api.saveStrategy({ ...copy, flow: studio.flow, filter_rules_code: await studio.compile() });
    reload();
    openStrategy(copy);
    toast('已复制');
  };

  const exportJson = async () => {
    if (!draft) return;
    const data = {
      ...draft,
      flow: mergeFlowForSave(originalFlowRef.current, studio.flow),
      filter_rules_code: await studio.compile(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `${draft.id}.json`;
    a.click();
  };

  const importJson = async (file) => {
    if (!file) return;
    try {
      const data = JSON.parse(await file.text());
      const res = await api.saveStrategy(data);
      if (!res.success) throw new Error(res.error);
      reload();
      openStrategy(data);
      toast('已导入');
    } catch (e) { toast(e.message, 'error'); }
  };

  const filterMode = draft?.filter_mode === 'flow' ? 'rules' : uiFilterMode(draft?.filter_mode || 'rules');
  const hideRulesTab = filterMode === 'code';

  const q = sidebarFilter.trim().toLowerCase();
  const filteredStrategies = q
    ? strategies.filter((s) => (s.name || '').toLowerCase().includes(q) || (s.id || '').toLowerCase().includes(q))
    : strategies;
  const filteredTemplates = q
    ? templates.filter((t) => (t.name || t.id || '').toLowerCase().includes(q))
    : templates;

  return (
    <div className={`admin-page strategy-page panel active${embedded ? ' strategy-page-embedded' : ''}`} id="panel-admin">
      {!embedded && (
        <>
        <SceneHubNav variant="query" />
        <header className="strategy-header">
          <div>
            <div className="topbar-title">查询策略</div>
            <p className="strategy-header-desc">策略 · 块模板 · Pipeline 筛选规则 · Python 后处理</p>
          </div>
          <div className="strategy-header-stats">
            <div className="strategy-stat">
              <span className="strategy-stat-value">{strategies.length}</span>
              <span className="strategy-stat-label">策略</span>
            </div>
            <div className="strategy-stat">
              <span className="strategy-stat-value">{templates.length}</span>
              <span className="strategy-stat-label">块模板</span>
            </div>
          </div>
        </header>
        </>
      )}

      <div className="strategy-layout">
        <aside className="strategy-sidebar">
          <div className="strategy-sidebar-head">
            <button type="button" className="btn btn-sm btn-primary strategy-new-btn" onClick={newStrategy}>+ 新建策略</button>
            <input
              className="strategy-sidebar-search"
              placeholder="搜索策略 / 模板…"
              value={sidebarFilter}
              onChange={(e) => setSidebarFilter(e.target.value)}
            />
          </div>

          <div className="strategy-sidebar-section">
            <div className="strategy-sidebar-label">策略 ({filteredStrategies.length})</div>
            <div className="strategy-list">
              {filteredStrategies.map((s) => (
                <SidebarItem
                  key={s.id}
                  active={editing?.type === 'strategy' && editing?.id === s.id}
                  onClick={() => openStrategy(s)}
                  title={s.name}
                  meta={s.category || 'custom'}
                  badge={s.category === '推荐' ? '推荐' : null}
                />
              ))}
              {!filteredStrategies.length && <div className="strategy-list-empty">无匹配策略</div>}
            </div>
          </div>

          <div className="strategy-sidebar-section">
            <div className="strategy-sidebar-label-row">
              <span className="strategy-sidebar-label">块模板 ({filteredTemplates.length})</span>
              <button type="button" className="btn btn-sm btn-ghost" onClick={newTemplate}>+ 新建</button>
            </div>
            <div className="strategy-list">
              {filteredTemplates.map((t) => (
                <SidebarItem
                  key={t.id}
                  active={editing?.type === 'template' && editing?.id === t.id}
                  onClick={() => { setEditing({ type: 'template', id: t.id }); setDraft({ ...t }); setEditorTab('meta'); }}
                  title={t.name || t.id}
                  meta={t.id}
                  badge={String(t.id).startsWith('_') ? '库' : null}
                />
              ))}
              {!filteredTemplates.length && <div className="strategy-list-empty">无匹配模板</div>}
            </div>
          </div>
        </aside>

        <main className="strategy-editor">
          {!draft ? (
            <EmptyEditor />
          ) : editing?.type === 'template' ? (
            <div className="strategy-editor-inner">
              <div className="strategy-editor-toolbar">
                <div>
                  <h2 className="strategy-editor-title">{draft.name || draft.id}</h2>
                  <p className="strategy-editor-sub">块模板 · 可复用的 Pipeline 筛选块</p>
                </div>
                <div className="strategy-editor-toolbar-actions">
                  <button type="button" className="btn btn-sm btn-primary" onClick={async () => {
                    const res = await api.saveTemplate(draft);
                    if (res.success) { toast('模板已保存'); reload(); }
                  }}>保存</button>
                  {!String(draft.id).startsWith('_') && (
                    <button type="button" className="btn btn-sm btn-ghost strategy-action-danger" onClick={async () => {
                      await api.deleteTemplate(draft.id);
                      setDraft(null);
                      reload();
                      toast('已删除');
                    }}>删除</button>
                  )}
                </div>
              </div>
              <div className="platform-surface-card strategy-panel">
                <TemplateEditor draft={draft} onChange={setDraft} />
              </div>
            </div>
          ) : (
            <div className="strategy-editor-inner">
              <div className="strategy-editor-toolbar">
                <div>
                  <div className="strategy-editor-title-row">
                    <h2 className="strategy-editor-title">{draft.name}</h2>
                    <span className="strategy-pill strategy-pill-info">{FILTER_MODE_LABEL[filterMode] || filterMode}</span>
                  </div>
                  <p className="strategy-editor-sub"><code>{draft.id}</code></p>
                </div>
                <div className="strategy-editor-toolbar-actions">
                  <button type="button" className="btn btn-sm btn-primary" onClick={saveDraft}>保存</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={duplicate}>复制</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={exportJson}>导出</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => document.getElementById('admin-import')?.click()}>导入</button>
                  <input id="admin-import" type="file" accept=".json" hidden onChange={(e) => { importJson(e.target.files?.[0]); e.target.value = ''; }} />
                  <Link className="btn btn-sm btn-ghost" to="/">主界面 →</Link>
                  <button type="button" className="btn btn-sm btn-ghost strategy-action-danger" onClick={() => setDeleteOpen(true)}>删除</button>
                </div>
              </div>

              <StrategyEditorTabBar activeTab={editorTab} onTabChange={setEditorTab} hideRules={hideRulesTab} />

              <div className="platform-surface-card strategy-panel">
                {editorTab === 'meta' && (
                  <div className="strategy-meta-form">
                    <div className="form-row">
                      <div className="form-group"><label>ID</label><input className="form-input" value={draft.id} onChange={(e) => setDraft({ ...draft, id: e.target.value })} /></div>
                      <div className="form-group"><label>名称</label><input className="form-input" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><label>筛选模式</label>
                        <select className="form-select" value={filterMode} onChange={(e) => setDraft({ ...draft, filter_mode: e.target.value })}>
                          <option value="rules">仅规则</option>
                          <option value="code">仅代码</option>
                        </select>
                      </div>
                      <div className="form-group"><label>分类</label><input className="form-input" value={draft.category || ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group form-group-wide"><label>描述</label><input className="form-input" value={draft.description || ''} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>数据源 data_source</label>
                        <select
                          className="form-select"
                          value={draft.data_source === 'predict_result' ? 'predict_result' : 'detail'}
                          onChange={(e) => {
                            const data_source = e.target.value;
                            setDraft({
                              ...draft,
                              data_source,
                              ...(data_source !== 'predict_result' ? { default_predict_job_id: undefined } : {}),
                            });
                          }}
                        >
                          {STRATEGY_DATA_SOURCES.map((opt) => (
                            <option key={opt.id} value={opt.id}>{opt.label}</option>
                          ))}
                        </select>
                      </div>
                      {draft.data_source === 'predict_result' && (
                        <div className="form-group">
                          <label>默认预测批次 ID（可选）</label>
                          <input
                            className="form-input"
                            type="number"
                            min={1}
                            placeholder="留空则查询页自动匹配最近批次"
                            value={draft.default_predict_job_id ?? ''}
                            onChange={(e) => {
                              const v = e.target.value.trim();
                              setDraft({
                                ...draft,
                                default_predict_job_id: v ? Number(v) : undefined,
                              });
                            }}
                          />
                        </div>
                      )}
                    </div>
                    <div className="form-row">
                      <div className="form-group">
                        <label>查询页默认视图</label>
                        <select
                          className="form-select"
                          value={draft.query_ui_mode === 'compact' ? 'compact' : 'full'}
                          onChange={(e) => setDraft({ ...draft, query_ui_mode: e.target.value })}
                        >
                          <option value="full">完整 — SQL / 规则 / Python 可编辑</option>
                          <option value="compact">简洁 — 参数 + 筛选规则（可配置隐藏项）</option>
                        </select>
                      </div>
                    </div>
                    {draft.query_ui_mode === 'compact' && (
                      <div className="form-row form-row-stack">
                        <div className="form-group form-group-wide">
                          <label>简洁模式隐藏项</label>
                          <QueryCompactHideEditor
                            value={draft.query_compact_hide || {}}
                            onChange={(query_compact_hide) => setDraft({ ...draft, query_compact_hide })}
                          />
                        </div>
                      </div>
                    )}
                    <p className="muted strategy-panel-hint">
                      <strong>数据源</strong>在策略中写定后，查询页加载该策略会自动切换明细表/预测结果表及 SQL，无需操作员再选。
                      采样数量、随机种子等业务参数请在「可调参数」页配置（如 SAMPLE_SIZE、RANDOM_SEED）。
                    </p>
                  </div>
                )}
                {editorTab === 'params' && (
                  <StrategyEnvSchemaEditor draft={draft} onChange={setDraft} templates={Object.fromEntries(templates.map((t) => [t.id, t]))} />
                )}
                {editorTab === 'sql' && (
                  <div className="strategy-code-panel">
                    <p className="strategy-panel-hint">支持 <code>${'${START_TIME}'}</code>、<code>${'${END_TIME}'}</code> 等变量占位符。</p>
                    <div className="editor-wrap strategy-editor-wrap"><SqlEditor value={draft.sql_template || ''} onChange={(v) => setDraft({ ...draft, sql_template: v })} /></div>
                  </div>
                )}
                {editorTab === 'rules' && filterMode !== 'code' && (
                  <div className="admin-rules-section strategy-rules-panel">
                    <RulesBuilder studio={studio} showCodePreview keyboardActive={false} />
                  </div>
                )}
                {editorTab === 'code' && (
                  <div className="strategy-code-panel">
                    <ProcessPipelineEditor
                      draft={draft}
                      onChange={setDraft}
                      templatesMap={Object.fromEntries(templates.map((t) => [t.id, t]))}
                    />
                    <div className="strategy-process-code-section">
                      <div className="strategy-process-code-head">
                        <h3 className="strategy-env-schema-title">process_data 源码</h3>
                        {draft.python_code_manual && (
                          <span className="strategy-pill strategy-pill-info">手写模式</span>
                        )}
                      </div>
                      <p className="strategy-panel-hint">
                        直接编辑并保存；与调用链不一致时自动按手写保留。要用调用链生成请点击上方「应用调用链到代码」。
                      </p>
                      <div className="editor-wrap strategy-editor-wrap">
                        <PythonEditor
                          value={draft.python_code || ''}
                          onChange={(v) => setDraft({ ...draft, python_code: v, python_code_manual: true })}
                        />
                      </div>
                    </div>
                  </div>
                )}
                {editorTab === 'flow' && (
                  <div className="strategy-code-panel">
                    <p className="strategy-panel-hint">Pipeline Flow 结构（只读，由规则表自动生成）。</p>
                    <textarea className="form-textarea code-area code-area-tall strategy-flow-json" value={JSON.stringify(mergeFlowForSave(originalFlowRef.current, studio.flow), null, 2)} readOnly />
                  </div>
                )}
              </div>
            </div>
          )}
        </main>
      </div>

      <Modal open={deleteOpen} title="删除策略" onClose={() => setDeleteOpen(false)}>
        <div className="form-modal-body">
          <p>确认删除策略「{draft?.name}」？此操作不可撤销。</p>
          <div className="form-actions">
            <button type="button" className="btn btn-ghost" onClick={() => setDeleteOpen(false)}>取消</button>
            <button type="button" className="btn btn-danger" onClick={async () => {
              try {
                const res = await api.deleteStrategy(draft.id);
                if (!res.success) throw new Error(res.error);
                setDeleteOpen(false);
                setDraft(null);
                setEditing(null);
                reload();
                toast('已删除');
              } catch (e) {
                toast(e.message || '删除失败', 'error');
              }
            }}>删除</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
