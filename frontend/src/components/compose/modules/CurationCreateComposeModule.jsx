import { useEffect, useState } from 'react';
import { api } from '../../../api/client';
import StrategyEnvFields from '../../StrategyEnvFields';
import {
  buildStrategyEnvDefaults,
  loadStrategyEnv,
  saveStrategyEnv,
} from '../../../lib/envVars';

const INTENT_OPTIONS = [
  { id: 'replay_eval', label: '历史回跑评估' },
  { id: 'daily_ng', label: '每日 NG 筛选' },
  { id: 'customer_qc', label: '人工质检' },
];

const DISPOSITION_OPTIONS = [
  { id: 'ng_only', label: '有框（FP）' },
  { id: 'clean_only', label: '无框（FN）' },
  { id: 'all', label: '全部' },
];

/** 创建筛选批次 — 与结果页 / 筛选页一致的完整配置 */
export default function CurationCreateComposeModule({ value, onChange }) {
  const [strategies, setStrategies] = useState([]);
  const [envSchema, setEnvSchema] = useState([]);
  const [env, setEnv] = useState(value?.env || {});

  useEffect(() => {
    api.getStrategies().then((r) => {
      if (r.success) setStrategies(r.data || []);
    }).catch(() => setStrategies([]));
  }, []);

  const strategyId = value?.strategy_id || '';

  useEffect(() => {
    if (!strategyId) {
      setEnvSchema([]);
      return;
    }
    Promise.all([
      api.getStrategyVariables(strategyId),
      api.getStrategy(strategyId).catch(() => ({ success: false })),
    ]).then(([vRes, sRes]) => {
      const schema = vRes.data?.custom_vars || [];
      setEnvSchema(schema);
      const meta = sRes.success ? (sRes.data || {}) : {};
      setEnv((prev) => ({ ...buildStrategyEnvDefaults(schema, meta, loadStrategyEnv(strategyId)), ...prev }));
    }).catch(() => setEnvSchema([]));
  }, [strategyId]);

  const set = (key, val) => onChange({ ...value, [key]: val });

  const setEnvField = (nextEnv) => {
    setEnv(nextEnv);
    onChange({ ...value, env: nextEnv });
    if (strategyId) saveStrategyEnv(strategyId, nextEnv);
  };

  return (
    <div className="compose-module-curation-create">
      <section className="platform-step platform-surface-card">
        <div className="platform-step-head">
          <span className="platform-step-num">1</span>
          <div>
            <h4>批次意图</h4>
            <p className="muted">决定后续导出、人工卡点与归档流程</p>
          </div>
        </div>
        <div className="forge-form-grid platform-predict-form">
          <label className="forge-span2">
            意图类型
            <select
              value={value?.intent_type || 'replay_eval'}
              onChange={(e) => set('intent_type', e.target.value)}
            >
              {INTENT_OPTIONS.map((o) => (
                <option key={o.id} value={o.id}>{o.label}</option>
              ))}
            </select>
          </label>
          <label>
            复核人
            <input
              type="text"
              value={value?.reviewer || ''}
              onChange={(e) => set('reviewer', e.target.value)}
              placeholder="可选"
            />
          </label>
          <label>
            备注
            <input
              type="text"
              value={value?.note || ''}
              onChange={(e) => set('note', e.target.value)}
              placeholder="可选"
            />
          </label>
        </div>
      </section>

      <section className="platform-step platform-surface-card">
        <div className="platform-step-head">
          <span className="platform-step-num">2</span>
          <div>
            <h4>策略（可选）</h4>
            <p className="muted">关联策略名称与可调参数，便于复现筛选条件</p>
          </div>
        </div>
        <div className="forge-form-grid platform-predict-form">
          <label className="forge-span2">
            策略
            <select
              value={strategyId}
              onChange={(e) => set('strategy_id', e.target.value)}
            >
              <option value="">不关联策略</option>
              {strategies.map((s) => (
                <option key={s.id} value={s.id}>{s.name || s.id}</option>
              ))}
            </select>
          </label>
          <label>
            数据来源
            <select
              value={value?.data_source || 'predict_result'}
              onChange={(e) => set('data_source', e.target.value)}
            >
              <option value="predict_result">预测结果表</option>
              <option value="detail">检测明细表</option>
            </select>
          </label>
        </div>
        {strategyId && envSchema.length > 0 && (
          <StrategyEnvFields
            strategyId={strategyId}
            schema={envSchema}
            values={env}
            onChange={setEnvField}
            compact
          />
        )}
      </section>

      {(value?.intent_type || 'replay_eval') === 'replay_eval' && (
        <section className="platform-step platform-surface-card">
          <div className="platform-step-head">
            <span className="platform-step-num">3</span>
            <div>
              <h4>回跑样本划分</h4>
              <p className="muted">创建批次后按预测框情况自动标记留/剔</p>
            </div>
          </div>
          <div className="replay-mode-tabs">
            {DISPOSITION_OPTIONS.map((m) => (
              <button
                key={m.id}
                type="button"
                className={`replay-mode-tab${(value?.replay_disposition_mode || 'ng_only') === m.id ? ' is-active' : ''}`}
                onClick={() => set('replay_disposition_mode', m.id)}
              >
                {m.label}
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
