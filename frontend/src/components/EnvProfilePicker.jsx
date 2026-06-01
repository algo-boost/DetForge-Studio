import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client';
import { envSummary, mergeEnvOverrides, profileVarsToEnv } from '../lib/envVars';

/** 查询 / 回跑共用：选择环境变量模版 + 临时覆盖 */
export default function EnvProfilePicker({
  label = '参数模版',
  strategyId,
  profileId,
  onProfileIdChange,
  onResolvedEnv,
  compact = false,
  testId,
}) {
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeProfile, setActiveProfile] = useState(null);
  const [overrides, setOverrides] = useState({});
  const onResolvedRef = useRef(onResolvedEnv);
  onResolvedRef.current = onResolvedEnv;

  const reload = useCallback(() => {
    setLoading(true);
    api.listEnvProfiles()
      .then((r) => setProfiles(r.data || []))
      .catch(() => setProfiles([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { reload(); }, [reload]);

  const filtered = useMemo(() => {
    if (!strategyId) return profiles;
    return profiles.filter((p) => {
      const hints = p.strategy_hints || [];
      return !hints.length || hints.includes(strategyId);
    });
  }, [profiles, strategyId]);

  useEffect(() => {
    setOverrides({});
    if (!profileId) {
      setActiveProfile(null);
      return;
    }
    api.getEnvProfile(profileId)
      .then((r) => setActiveProfile(r.data))
      .catch(() => setActiveProfile(null));
  }, [profileId]);

  const baseEnv = useMemo(() => profileVarsToEnv(activeProfile), [activeProfile]);
  const resolvedEnv = useMemo(
    () => mergeEnvOverrides(baseEnv, overrides),
    [baseEnv, overrides],
  );

  useEffect(() => {
    onResolvedRef.current?.(resolvedEnv);
  }, [resolvedEnv]);

  useEffect(() => {
    if (profileId || !strategyId || !filtered.length) return;
    const hinted = filtered.find((p) => (p.strategy_hints || []).includes(strategyId));
    const pick = hinted || filtered[0];
    if (pick?.id) onProfileIdChange?.(pick.id);
  }, [strategyId, filtered, profileId, onProfileIdChange]);

  const vars = activeProfile?.vars || [];

  const handleFieldChange = (key, val) => {
    const k = String(key).toUpperCase();
    setOverrides((prev) => ({ ...prev, [k]: val }));
  };

  return (
    <div className={`env-profile-picker${compact ? ' is-compact' : ''}`} data-testid={testId}>
      <div className="env-profile-picker-head">
        <label className="env-profile-picker-label">
          {label}
          <select
            value={profileId || ''}
            disabled={loading}
            onChange={(e) => onProfileIdChange?.(e.target.value || '')}
            data-testid={testId ? `${testId}-select` : undefined}
          >
            <option value="">{loading ? '加载中…' : '选择参数模版…'}</option>
            {filtered.map((p) => (
              <option key={p.id} value={p.id}>{p.name || p.id}</option>
            ))}
          </select>
        </label>
        <Link to={profileId ? `/env-profiles?id=${encodeURIComponent(profileId)}` : '/env-profiles'} className="btn btn-sm btn-ghost">
          管理模版
        </Link>
        {strategyId && (
          <Link
            to={`/env-profiles?new=1&strategy=${encodeURIComponent(strategyId)}`}
            className="btn btn-sm btn-ghost"
          >
            + 新建
          </Link>
        )}
      </div>

      {!profileId && (
        <p className="muted env-profile-picker-empty">
          请先在
          {' '}
          <Link to="/env-profiles">环境变量</Link>
          {' '}
          页创建模版；策略 SQL/Python 通过
          {' '}
          <code>{'${KEY}'}</code>
          {' '}
          /
          {' '}
          <code>get_env('KEY')</code>
          {' '}
          引用。
        </p>
      )}

      {profileId && vars.length > 0 && (
        <div className="env-profile-picker-fields">
          {vars.map((field) => (
            <label key={field.key} className="env-profile-field">
              <span>{field.label || field.key}</span>
              <input
                type={field.type === 'number' ? 'number' : 'text'}
                step={field.type === 'number' ? '0.01' : undefined}
                placeholder={field.description || field.key}
                value={overrides[field.key] ?? field.value ?? ''}
                onChange={(e) => handleFieldChange(field.key, e.target.value)}
                data-testid={`env-field-${field.key}`}
              />
            </label>
          ))}
        </div>
      )}

      {profileId && vars.length === 0 && (
        <p className="muted env-profile-picker-empty">该模版暂无变量，可在「管理模版」中添加。</p>
      )}

      {profileId && (
        <p className="muted env-profile-picker-summary" data-testid={testId ? `${testId}-summary` : undefined}>
          生效：{envSummary(resolvedEnv)}
        </p>
      )}
    </div>
  );
}
