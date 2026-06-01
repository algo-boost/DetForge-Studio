import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, toast } from '../api/client';
import SceneHubNav from '../components/SceneHubNav';
import { envSummary, newVarRow } from '../lib/envVars';

const EMPTY_PROFILE = {
  id: '',
  name: '',
  description: '',
  strategy_hints: [],
  vars: [],
};

function slugify(text) {
  return String(text || '')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '_')
    .replace(/^_+|_+$/g, '')
    .slice(0, 48);
}

export default function EnvProfilesPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [profiles, setProfiles] = useState([]);
  const [strategies, setStrategies] = useState([]);
  const [selectedId, setSelectedId] = useState(searchParams.get('id') || '');
  const [draft, setDraft] = useState({ ...EMPTY_PROFILE });
  const [busy, setBusy] = useState(false);

  const loadList = useCallback(async () => {
    const [pRes, sRes] = await Promise.all([
      api.listEnvProfiles().catch(() => ({ data: [] })),
      api.getStrategies().catch(() => ({ data: [] })),
    ]);
    setProfiles(pRes.data || []);
    setStrategies(sRes.data || []);
  }, []);

  useEffect(() => { loadList(); }, [loadList]);

  useEffect(() => {
    const id = searchParams.get('id');
    const isNew = searchParams.get('new') === '1';
    const strategyHint = searchParams.get('strategy');
    if (id) {
      setSelectedId(id);
      api.getEnvProfile(id).then((r) => setDraft(r.data)).catch(() => toast('模版不存在', 'error'));
      return;
    }
    if (isNew) {
      setSelectedId('');
      const base = {
        ...EMPTY_PROFILE,
        id: strategyHint ? `${strategyHint}_params` : `profile_${Date.now()}`,
        name: strategyHint ? `${strategyHint} 参数` : '新参数模版',
        strategy_hints: strategyHint ? [strategyHint] : [],
      };
      setDraft(base);
      if (strategyHint) {
        api.suggestEnvProfileVars({ strategy_id: strategyHint })
          .then((r) => setDraft((d) => ({ ...d, vars: r.data || [] })))
          .catch(() => {});
      }
    }
  }, [searchParams]);

  const selectProfile = (p) => {
    setSelectedId(p.id);
    setDraft({ ...p, vars: [...(p.vars || [])] });
    setSearchParams({ id: p.id });
  };

  const startNew = () => {
    setSelectedId('');
    setDraft({
      ...EMPTY_PROFILE,
      id: `profile_${Date.now()}`,
      name: '新参数模版',
      vars: [newVarRow('MIN_SCORE', '最低分数')],
    });
    setSearchParams({ new: '1' });
  };

  const updateDraft = (patch) => setDraft((d) => ({ ...d, ...patch }));

  const updateVar = (idx, patch) => {
    setDraft((d) => ({
      ...d,
      vars: d.vars.map((row, i) => (i === idx ? { ...row, ...patch, key: String((patch.key ?? row.key)).toUpperCase() } : row)),
    }));
  };

  const addVar = () => setDraft((d) => ({ ...d, vars: [...(d.vars || []), newVarRow()] }));
  const removeVar = (idx) => setDraft((d) => ({ ...d, vars: d.vars.filter((_, i) => i !== idx) }));

  const toggleStrategyHint = (sid) => {
    setDraft((d) => {
      const hints = new Set(d.strategy_hints || []);
      if (hints.has(sid)) hints.delete(sid);
      else hints.add(sid);
      return { ...d, strategy_hints: [...hints] };
    });
  };

  const suggestFromStrategies = async () => {
    const ids = draft.strategy_hints?.length ? draft.strategy_hints : strategies.map((s) => s.id);
    try {
      const r = await api.suggestEnvProfileVars({ strategy_ids: ids.slice(0, 10) });
      const suggested = r.data || [];
      const existing = new Set((draft.vars || []).map((v) => v.key));
      const merged = [...(draft.vars || [])];
      suggested.forEach((row) => {
        if (!existing.has(row.key)) merged.push(row);
      });
      setDraft((d) => ({ ...d, vars: merged }));
      toast(`已合并 ${suggested.length} 个建议变量`, 'success');
    } catch (e) {
      toast(e.message, 'error');
    }
  };

  const save = async () => {
    const id = (draft.id || slugify(draft.name) || `profile_${Date.now()}`).trim();
    if (!draft.name?.trim()) {
      toast('请填写模版名称', 'error');
      return;
    }
    setBusy(true);
    try {
      const payload = { ...draft, id, vars: (draft.vars || []).filter((v) => v.key?.trim()) };
      const r = await api.saveEnvProfile(payload);
      toast('已保存', 'success');
      setDraft(r.data);
      setSelectedId(r.data.id);
      setSearchParams({ id: r.data.id });
      await loadList();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!selectedId || !window.confirm(`删除模版「${draft.name}」？`)) return;
    setBusy(true);
    try {
      await api.deleteEnvProfile(selectedId);
      toast('已删除', 'success');
      setSelectedId('');
      setDraft({ ...EMPTY_PROFILE });
      setSearchParams({});
      await loadList();
    } catch (e) {
      toast(e.message, 'error');
    } finally {
      setBusy(false);
    }
  };

  const previewEnv = useMemo(() => {
    const out = {};
    (draft.vars || []).forEach((row) => {
      if (row.key && row.value != null && String(row.value).trim() !== '') {
        out[row.key] = String(row.value).trim();
      }
    });
    return out;
  }, [draft.vars]);

  return (
    <div className="panel active env-profiles-page" data-testid="env-profiles-page">
      <div className="topbar">
        <div className="topbar-left-group">
          <SceneHubNav variant="query" className="scene-hub-nav-inline" />
          <div>
            <div className="topbar-title">环境变量</div>
            <div className="topbar-sub">参数模版 · 查询与历史回跑共用 · SQL {'${VAR}'} / Python get_env()</div>
          </div>
        </div>
        <div className="topbar-actions">
          <button type="button" className="btn btn-primary btn-sm" onClick={startNew}>+ 新建模版</button>
        </div>
      </div>

      <div className="env-profiles-layout">
        <aside className="env-profiles-list">
          <h3>模版列表</h3>
          {profiles.length === 0 ? (
            <p className="muted">暂无模版，点击右上角新建。</p>
          ) : (
            <ul>
              {profiles.map((p) => (
                <li key={p.id}>
                  <button
                    type="button"
                    className={`env-profile-list-item${selectedId === p.id ? ' is-active' : ''}`}
                    onClick={() => selectProfile(p)}
                  >
                    <strong>{p.name || p.id}</strong>
                    <span className="muted">{envSummary(
                      Object.fromEntries((p.vars || []).filter((v) => v.key && v.value).map((v) => [v.key, v.value])),
                    )}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <main className="env-profiles-editor">
          <div className="env-profiles-editor-head">
            <h3>{selectedId ? '编辑模版' : '新建模版'}</h3>
            <div className="env-profiles-editor-actions">
              <button type="button" className="btn btn-secondary btn-sm" onClick={suggestFromStrategies} disabled={busy}>
                从策略推断变量
              </button>
              <button type="button" className="btn btn-primary btn-sm" onClick={save} disabled={busy}>
                {busy ? '保存中…' : '保存'}
              </button>
              {selectedId && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={remove} disabled={busy}>删除</button>
              )}
            </div>
          </div>

          <div className="env-profiles-form-grid">
            <label>
              模版 ID
              <input value={draft.id} onChange={(e) => updateDraft({ id: e.target.value })} placeholder="如 replay_yanfeng" />
            </label>
            <label>
              显示名称
              <input value={draft.name} onChange={(e) => updateDraft({ name: e.target.value })} placeholder="如 延锋回跑默认参数" />
            </label>
            <label className="env-profiles-span2">
              说明
              <input value={draft.description || ''} onChange={(e) => updateDraft({ description: e.target.value })} placeholder="用途说明（可选）" />
            </label>
          </div>

          <div className="env-profiles-strategies">
            <span className="env-profiles-strategies-label">关联策略（便于筛选）</span>
            <div className="env-profiles-strategy-chips">
              {strategies.slice(0, 24).map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className={`env-strategy-chip${(draft.strategy_hints || []).includes(s.id) ? ' is-on' : ''}`}
                  onClick={() => toggleStrategyHint(s.id)}
                >
                  {s.name || s.id}
                </button>
              ))}
            </div>
          </div>

          <div className="env-profiles-vars">
            <div className="env-profiles-vars-head">
              <h4>变量定义</h4>
              <button type="button" className="btn btn-sm btn-ghost" onClick={addVar}>+ 添加变量</button>
            </div>
            <div className="env-profiles-vars-table">
              <div className="env-profiles-vars-row env-profiles-vars-header">
                <span>KEY</span><span>标签</span><span>类型</span><span>默认值</span><span />
              </div>
              {(draft.vars || []).map((row, idx) => (
                <div key={`${row.key}-${idx}`} className="env-profiles-vars-row">
                  <input
                    value={row.key}
                    placeholder="MIN_SCORE"
                    onChange={(e) => updateVar(idx, { key: e.target.value.toUpperCase() })}
                  />
                  <input
                    value={row.label || ''}
                    placeholder="显示名"
                    onChange={(e) => updateVar(idx, { label: e.target.value })}
                  />
                  <select value={row.type || 'text'} onChange={(e) => updateVar(idx, { type: e.target.value })}>
                    <option value="text">文本</option>
                    <option value="number">数字</option>
                  </select>
                  <input
                    value={row.value ?? ''}
                    placeholder="默认值"
                    onChange={(e) => updateVar(idx, { value: e.target.value })}
                  />
                  <button type="button" className="btn btn-sm btn-ghost" onClick={() => removeVar(idx)}>删</button>
                </div>
              ))}
            </div>
          </div>

          <div className="env-profiles-preview">
            <strong>预览生效值：</strong>
            <code>{envSummary(previewEnv)}</code>
          </div>

          <div className="env-profiles-usage muted">
            <p>在策略 SQL 中写 <code>{'${MIN_SCORE}'}</code>；Python 中写 <code>get_env('MIN_SCORE', '0.1')</code>。</p>
            <p>
              查询页与
              {' '}
              <Link to="/curation?replay=1">历史回跑</Link>
              {' '}
              选择本模版即可注入参数，无需重复配置。
            </p>
          </div>
        </main>
      </div>
    </div>
  );
}
