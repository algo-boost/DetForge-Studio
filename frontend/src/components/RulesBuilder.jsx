import { useCallback, useEffect, useRef, useState } from 'react';
import { api, toast } from '../api/client';
import { CategorySelect } from './CategorySelect';

export function RulesBuilder({ studio, showCodePreview = false, complexHint = false, keyboardActive = true }) {
  const {
    rules, setRules, removeEmpty, setRemoveEmpty, categoryOptions,
    loadBuiltinTemplate, loadSavedTemplate, saveAsTemplate, getSavedTemplates,
    importPipelineRules, newRule, isMinThresholdRule, compiledCode,
  } = studio;

  const [pipelines, setPipelines] = useState([]);
  const [pipelineId, setPipelineId] = useState('');
  const [nodeId, setNodeId] = useState('');
  const [nodes, setNodes] = useState([]);
  const [trawl, setTrawl] = useState(true);
  const [pipelineOpen, setPipelineOpen] = useState(false);
  const [selected, setSelected] = useState(new Set());
  const [batchMin, setBatchMin] = useState(0);
  const [batchMax, setBatchMax] = useState(1);
  const [batchDrop, setBatchDrop] = useState(1);
  const [dragIndex, setDragIndex] = useState(-1);
  const [dragOverIndex, setDragOverIndex] = useState(-1);
  const listRef = useRef(null);

  const loadPipelines = async () => {
    if (pipelines.length) return;
    const res = await api.getPipelines();
    if (res.success) setPipelines(res.pipelines || []);
  };

  const onPipelineChange = async (id) => {
    setPipelineId(id);
    setNodeId('');
    if (!id) { setNodes([]); return; }
    const res = await api.getPipelineNodes(id);
    setNodes(res.success ? (res.nodes || []) : []);
  };

  const updateRule = (i, patch) => {
    setRules((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  };

  const toggleMode = (i) => {
    const r = rules[i];
    if (!r) return;
    if (isMinThresholdRule(r)) {
      const lo = r.min_confidence ?? (r.confidence_range || [0, 1])[0];
      updateRule(i, {
        confidence_mode: undefined,
        min_confidence: undefined,
        confidence_range: [lo, 1],
        random_drop_ratio: 1,
      });
    } else {
      const lo = (r.confidence_range || [0, 1])[0];
      updateRule(i, {
        confidence_mode: 'min_threshold',
        min_confidence: lo,
        confidence_range: [lo, 1],
      });
    }
  };

  const dupRule = (i) => {
    setRules((prev) => {
      const copy = JSON.parse(JSON.stringify(prev[i]));
      const next = [...prev];
      next.splice(i + 1, 0, copy);
      return next;
    });
  };

  const moveRule = (i, dir) => {
    setRules((prev) => {
      const j = i + dir;
      if (j < 0 || j >= prev.length) return prev;
      const next = [...prev];
      [next[i], next[j]] = [next[j], next[i]];
      return next;
    });
  };

  const moveRuleTo = useCallback((from, to) => {
    if (from === to || from < 0 || to < 0) return;
    setRules((prev) => {
      if (from >= prev.length || to >= prev.length) return prev;
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      return next;
    });
    setSelected(new Set());
  }, [setRules]);

  const duplicateLastRule = useCallback(() => {
    setRules((prev) => {
      if (!prev.length) return prev;
      return [...prev, JSON.parse(JSON.stringify(prev[prev.length - 1]))];
    });
  }, [setRules]);

  useEffect(() => {
    if (!keyboardActive || !rules.length) return undefined;
    const onKey = (e) => {
      if (e.target.matches('input, textarea, select') || e.target.closest('.cm-editor')) return;

      if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        duplicateLastRule();
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.shiftKey && (e.key === 'a' || e.key === 'A')) {
        e.preventDefault();
        setSelected(new Set(rules.map((_, i) => i)));
        return;
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selected.size) {
        e.preventDefault();
        setRules((prev) => prev.filter((_, i) => !selected.has(i)));
        setSelected(new Set());
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [keyboardActive, rules.length, selected, duplicateLastRule, setRules]);

  const toggleCategory = (i, cats) => {
    updateRule(i, { categories: cats });
  };

  const applyBatch = () => {
    setRules((prev) => prev.map((r) => {
      const copy = { ...r };
      if (isMinThresholdRule(copy)) {
        copy.min_confidence = batchMin;
        copy.confidence_range = [batchMin, 1];
      } else {
        copy.confidence_range = [batchMin, batchMax];
        copy.random_drop_ratio = batchDrop;
      }
      return copy;
    }));
  };

  const deleteSelected = () => {
    if (!selected.size) return;
    setRules((prev) => prev.filter((_, i) => !selected.has(i)));
    setSelected(new Set());
  };

  const toggleSel = (i) => {
    setSelected((prev) => {
      const n = new Set(prev);
      if (n.has(i)) n.delete(i); else n.add(i);
      return n;
    });
  };

  if (!rules.length) {
    return (
      <div className="rules-empty">
        <p>日常捞图：加载模板，按类别调整置信度区间与剔除比例，先预览再执行。</p>
        <div className="rules-empty-actions">
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => loadBuiltinTemplate('daily_trawl')}>日常捞图</button>
          <button type="button" className="btn btn-ghost btn-sm" onClick={() => loadBuiltinTemplate('high_conf')}>高置信</button>
          <button type="button" className="btn btn-primary" onClick={() => setRules([newRule()])}>+ 添加规则</button>
        </div>
      </div>
    );
  }

  const saved = getSavedTemplates();

  return (
    <div className="rules-builder">
      {complexHint && (
        <div className="rules-complex-hint">当前策略还包含预处理、采样等步骤；此处仅编辑筛选规则，其余节点不受影响。</div>
      )}
      <div className="rules-builder-bar">
        <div className="rules-builder-title">
          <span className="rb-title">筛选规则</span>
          <span className="rb-sub">依次应用 · {rules.length} 条规则</span>
        </div>
        <div className="rules-builder-actions">
          <select className="rules-template-select" defaultValue="" onChange={(e) => { if (e.target.value) loadBuiltinTemplate(e.target.value); e.target.value = ''; }}>
            <option value="">内置模板…</option>
            <option value="daily_trawl">日常捞图</option>
            <option value="high_conf">高置信缺陷</option>
          </select>
          <select className="rules-template-select" defaultValue="" onChange={(e) => { if (e.target.value) loadSavedTemplate(e.target.value); e.target.value = ''; }}>
            <option value="">我的模板…</option>
            {saved.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => {
            const name = window.prompt('规则模板名称', `捞图规则_${new Date().toISOString().slice(0, 10)}`);
            if (name) { saveAsTemplate(name); toast(`已保存：${name}`); }
          }}>存模板</button>
          <label className="rb-toggle">
            <input type="checkbox" checked={removeEmpty} onChange={(e) => setRemoveEmpty(e.target.checked)} />
            <span>移除空框行</span>
            <span className="muted rules-hint-inline" title="仅丢弃筛选后 ext 里没有任何检测框的图片；保留的图片不删框">
              （只丢无框图，保留图内全部框）
            </span>
          </label>
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setRules((r) => [...r, newRule()])}>+ 添加规则</button>
          <details className="rules-pipeline-details" open={pipelineOpen} onToggle={(e) => { setPipelineOpen(e.target.open); if (e.target.open) loadPipelines(); }}>
            <summary className="rules-pipeline-summary">Pipeline 导入</summary>
            <div className="rules-pipeline-inner">
              <select className="rules-template-select" value={pipelineId} onChange={(e) => onPipelineChange(e.target.value)}>
                <option value="">Pipeline…</option>
                {pipelines.map((p) => <option key={p.id} value={p.id}>{p.name || p.id}</option>)}
              </select>
              <select className="rules-template-select" value={nodeId} onChange={(e) => setNodeId(e.target.value)}>
                <option value="">全部节点</option>
                {nodes.map((n) => <option key={n.id} value={n.id}>{n.name || n.id}</option>)}
              </select>
              <label className="rb-toggle rb-toggle-inline">
                <input type="checkbox" checked={trawl} onChange={(e) => setTrawl(e.target.checked)} />
                <span>捞图剔除</span>
              </label>
              <button type="button" className="btn btn-sm btn-ghost" onClick={async () => {
                if (!pipelineId) { toast('请选择 Pipeline', 'error'); return; }
                try {
                  const res = await importPipelineRules(pipelineId, nodeId, trawl);
                  toast(`已导入 ${(res.rules || []).length} 条规则`);
                } catch (e) { toast(e.message, 'error'); }
              }}>导入</button>
            </div>
          </details>
        </div>
      </div>
      {rules.length > 0 && (
        <div className="rules-batch-bar">
          <span className="rules-batch-label">批量</span>
          <label className="rules-batch-field">置信度
            <input type="number" min={0} max={1} step={0.05} value={batchMin} onChange={(e) => setBatchMin(+e.target.value)} />
            <span>~</span>
            <input type="number" min={0} max={1} step={0.05} value={batchMax} onChange={(e) => setBatchMax(+e.target.value)} />
          </label>
          <label className="rules-batch-field">剔除
            <input type="range" min={0} max={1} step={0.05} value={batchDrop} onChange={(e) => setBatchDrop(+e.target.value)} />
            <em>{Math.round(batchDrop * 100)}%</em>
          </label>
          <button type="button" className="btn btn-sm btn-ghost" onClick={applyBatch}>应用到全部</button>
          <button type="button" className="btn btn-sm btn-ghost" onClick={() => { if (rules.length) dupRule(rules.length - 1); }}>复制最后一条</button>
          <button type="button" className="btn btn-sm btn-ghost" disabled={!selected.size} onClick={deleteSelected}>删除选中</button>
          <label className="rules-batch-select-all" title="全选规则 (Ctrl+Shift+A)">
            <input type="checkbox" checked={selected.size === rules.length && rules.length > 0} onChange={(e) => setSelected(e.target.checked ? new Set(rules.map((_, i) => i)) : new Set())} /> 全选
          </label>
          <span className="rules-kbd-hint" title="快捷键">⌘D 复制 · Del 删除</span>
        </div>
      )}
      <div className="rules-list" ref={listRef}>
        {rules.map((r, i) => (
          <div
            className={`rule-row${selected.has(i) ? ' is-selected' : ''}${dragOverIndex === i ? ' rule-row-drag-over' : ''}${dragIndex === i ? ' rule-row-dragging' : ''}`}
            key={i}
            data-rule-index={i}
            onDragOver={(e) => {
              if (dragIndex < 0) return;
              e.preventDefault();
              setDragOverIndex(i);
            }}
            onDragLeave={() => setDragOverIndex((cur) => (cur === i ? -1 : cur))}
            onDrop={(e) => {
              e.preventDefault();
              if (dragIndex >= 0) moveRuleTo(dragIndex, i);
              setDragIndex(-1);
              setDragOverIndex(-1);
            }}
          >
            <span
              className="rule-row-drag"
              draggable
              title="拖拽排序"
              onDragStart={() => setDragIndex(i)}
              onDragEnd={() => { setDragIndex(-1); setDragOverIndex(-1); }}
            >
              ⠿
            </span>
            <input type="checkbox" className="rule-row-select" checked={selected.has(i)} onChange={() => toggleSel(i)} />
            <div className="rule-row-handle">
              <button type="button" className="rr-mv" disabled={i === 0} onClick={() => moveRule(i, -1)}>↑</button>
              <button type="button" className="rr-mv" disabled={i === rules.length - 1} onClick={() => moveRule(i, 1)}>↓</button>
              <button type="button" className="rr-dup" onClick={() => dupRule(i)}>复制</button>
            </div>
            <div className="rule-row-body">
              <div className="rule-tags rule-tags-select">
                <CategorySelect
                  options={categoryOptions}
                  selected={r.categories || []}
                  onChange={(cats) => toggleCategory(i, cats)}
                  placeholder="未选类别 · 规则不生效"
                />
              </div>
              {(r.positions || []).length > 0 && (
                <div className="rule-pos-row">
                  <span className="rule-pos-label">面别</span>
                  {(r.positions || []).map((p) => <span key={p} className="rt-tag rt-tag-readonly">{p}</span>)}
                </div>
              )}
              <div className="rule-fields">
                {isMinThresholdRule(r) ? (
                  <label>最低阈值
                    <input type="number" min={0} max={1} step={0.05} value={r.min_confidence ?? 0}
                      onChange={(e) => updateRule(i, { min_confidence: +e.target.value, confidence_range: [+e.target.value, 1] })} />
                  </label>
                ) : (
                  <>
                    <label>置信度
                      <input type="number" min={0} max={1} step={0.05} value={(r.confidence_range || [0, 1])[0]}
                        onChange={(e) => updateRule(i, { confidence_range: [+e.target.value, (r.confidence_range || [0, 1])[1]] })} />
                      <span>~</span>
                      <input type="number" min={0} max={1} step={0.05} value={(r.confidence_range || [0, 1])[1]}
                        onChange={(e) => updateRule(i, { confidence_range: [(r.confidence_range || [0, 1])[0], +e.target.value] })} />
                    </label>
                    <label>剔除
                      <input type="range" min={0} max={1} step={0.05} value={r.random_drop_ratio ?? 1}
                        onChange={(e) => updateRule(i, { random_drop_ratio: +e.target.value })} />
                      <em>{Math.round((r.random_drop_ratio ?? 1) * 100)}%</em>
                    </label>
                  </>
                )}
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => toggleMode(i)}>
                  {isMinThresholdRule(r) ? '⇄ 捞图' : '⇄ 产线'}
                </button>
                <button type="button" className="btn btn-sm btn-ghost" onClick={() => setRules((prev) => prev.filter((_, idx) => idx !== i))}>删除</button>
              </div>
            </div>
          </div>
        ))}
      </div>
      {showCodePreview && (
        <div className="rules-code-preview">
          <div className="rules-code-header">
            <span>apply_filter_rules（自动生成）</span>
            <button type="button" className="rules-code-copy" onClick={() => navigator.clipboard?.writeText(compiledCode || '')}>复制</button>
          </div>
          <pre className="rules-split-code">{compiledCode || '# 添加规则后将自动生成 apply_filter_rules(df)'}</pre>
        </div>
      )}
    </div>
  );
}
