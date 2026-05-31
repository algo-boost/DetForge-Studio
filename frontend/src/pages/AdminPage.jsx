import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, toast } from '../api/client';
import { RulesBuilder } from '../components/RulesBuilder';
import { SqlEditor, PythonEditor } from '../components/Editors';
import { useRulesStudio } from '../hooks/useRulesStudio';
import { TemplateEditor } from '../components/TemplateEditor';
import { Modal } from '../components/Modal';
import { mergeFlowForSave, uiFilterMode } from '../lib/flowMerge';
import { FILTER_MODE_LABEL, STRATEGY_EDITOR_TABS, isBuiltinStrategy } from '../components/strategy/strategyUtils';

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
    setDraft({ ...s, filter_mode: uiFilterMode(s.filter_mode || 'flow') });
    setEditorTab('meta');
    originalFlowRef.current = s.flow ? JSON.parse(JSON.stringify(s.flow)) : null;
    studio.setFlow(s.flow || { version: 2, nodes: [] });
  };

  const newStrategy = () => {
    const id = `saved_${Date.now()}`;
    const s = {
      id, name: '新策略', category: 'custom', filter_mode: 'split',
      sql_template: "SELECT * FROM product_detection_detail_result\nWHERE c_time BETWEEN '${START_TIME}' AND '${END_TIME}'",
      python_code: 'def process_data(df):\n    df = apply_filter_rules(df)\n    return df',
      flow: { version: 2, nodes: [] }, sample_size: 300,
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
    const mode = draft.filter_mode === 'flow' ? 'rules' : (draft.filter_mode || 'split');
    const payload = {
      ...draft,
      filter_mode: mode,
      flow: mergeFlowForSave(originalFlowRef.current, studio.flow),
      filter_rules_code: await studio.compile(),
    };
    try {
      const res = await api.saveStrategy(payload);
      if (!res.success) throw new Error(res.error);
      toast('已保存');
      reload();
    } catch (e) { toast(e.message, 'error'); }
  };

  const duplicate = async () => {
    if (!draft) return;
    const copy = { ...draft, id: `${draft.id}_copy_${Date.now()}`, name: `${draft.name} (副本)` };
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

  const isBuiltin = isBuiltinStrategy(draft);
  const filterMode = draft?.filter_mode === 'flow' ? 'rules' : (draft?.filter_mode || 'split');
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
                  badge={isBuiltinStrategy(s) ? '内置' : null}
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
                  badge={String(t.id).startsWith('_') ? '内置' : null}
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
                    {isBuiltin && <span className="strategy-pill strategy-pill-muted">内置</span>}
                    <span className="strategy-pill strategy-pill-info">{FILTER_MODE_LABEL[filterMode] || filterMode}</span>
                  </div>
                  <p className="strategy-editor-sub"><code>{draft.id}</code> · 采样 {draft.sample_size || 300}</p>
                </div>
                <div className="strategy-editor-toolbar-actions">
                  <button type="button" className="btn btn-sm btn-primary" onClick={saveDraft}>保存</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={duplicate}>复制</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={exportJson}>导出</button>
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => document.getElementById('admin-import')?.click()}>导入</button>
                  <input id="admin-import" type="file" accept=".json" hidden onChange={(e) => { importJson(e.target.files?.[0]); e.target.value = ''; }} />
                  <Link className="btn btn-sm btn-ghost" to="/">主界面 →</Link>
                  {!isBuiltin && <button type="button" className="btn btn-sm btn-ghost strategy-action-danger" onClick={() => setDeleteOpen(true)}>删除</button>}
                </div>
              </div>

              <StrategyEditorTabBar activeTab={editorTab} onTabChange={setEditorTab} hideRules={hideRulesTab} />

              <div className="platform-surface-card strategy-panel">
                {editorTab === 'meta' && (
                  <div className="strategy-meta-form">
                    <div className="form-row">
                      <div className="form-group"><label>ID</label><input className="form-input" value={draft.id} readOnly={isBuiltin} onChange={(e) => setDraft({ ...draft, id: e.target.value })} /></div>
                      <div className="form-group"><label>采样数量</label><input type="number" className="form-input" value={draft.sample_size || 300} onChange={(e) => setDraft({ ...draft, sample_size: +e.target.value })} /></div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><label>名称</label><input className="form-input" value={draft.name || ''} onChange={(e) => setDraft({ ...draft, name: e.target.value })} /></div>
                      <div className="form-group"><label>筛选模式</label>
                        <select className="form-select" value={filterMode} onChange={(e) => setDraft({ ...draft, filter_mode: e.target.value })}>
                          <option value="split">规则 + 代码</option>
                          <option value="rules">仅规则</option>
                          <option value="code">仅代码</option>
                        </select>
                      </div>
                    </div>
                    <div className="form-row">
                      <div className="form-group"><label>分类</label><input className="form-input" value={draft.category || ''} onChange={(e) => setDraft({ ...draft, category: e.target.value })} /></div>
                      <div className="form-group"><label>描述</label><input className="form-input" value={draft.description || ''} onChange={(e) => setDraft({ ...draft, description: e.target.value })} /></div>
                    </div>
                  </div>
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
                    <p className="strategy-panel-hint">定义 <code>process_data(df)</code> 函数，对 SQL 结果做后处理。</p>
                    <div className="editor-wrap strategy-editor-wrap"><PythonEditor value={draft.python_code || ''} onChange={(v) => setDraft({ ...draft, python_code: v })} /></div>
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
              await api.deleteStrategy(draft.id);
              setDeleteOpen(false);
              setDraft(null);
              setEditing(null);
              reload();
              toast('已删除');
            }}>删除</button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
