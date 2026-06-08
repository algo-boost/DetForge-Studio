import { useMemo, useState } from 'react';
import {
  buildStepsFromBlocks,
  paramsSchemaForBlocks,
  PRESET_BLOCKS,
  defaultParamsFromSchema,
} from '../../lib/workflowCatalog';
import WorkflowPipelineViz from './WorkflowPipelineViz';
import WorkflowParamsForm from './WorkflowParamsForm';

const BLOCK_OPTIONS = [
  { key: 'query', label: '查询筛选', desc: '从平台明细表捞图' },
  { key: 'predict', label: '模型预测', desc: '对捞图结果批量预测', needs: ['query'] },
  { key: 'query_predict', label: '预测结果二次筛选', desc: '误检/漏检评测策略', needs: ['predict'] },
  { key: 'curation', label: '筛选出站归档', desc: '建批次、导出、归档', needs: ['query'] },
  { key: 'human_gate', label: '人工上传 COCO', desc: '外部编辑后回传', needs: ['curation'] },
  { key: 'notify', label: '完成通知', desc: '飞书/邮件/站内', needs: [] },
];

function applyPreset(presetId) {
  return { ...(PRESET_BLOCKS[presetId] || PRESET_BLOCKS.daily_ng_curation) };
}

export default function WorkflowComposer({ models = [], onLaunch, busy = false }) {
  const [preset, setPreset] = useState('daily_ng_curation');
  const [blocks, setBlocks] = useState(applyPreset('daily_ng_curation'));
  const [params, setParams] = useState({});
  const [name, setName] = useState('');

  const schema = useMemo(() => paramsSchemaForBlocks(blocks), [blocks]);
  const steps = useMemo(() => buildStepsFromBlocks(blocks), [blocks]);

  const loadPreset = (id) => {
    setPreset(id);
    const b = applyPreset(id);
    setBlocks(b);
    const sch = paramsSchemaForBlocks(b);
    setParams(defaultParamsFromSchema(sch));
    if (id === 'weekly_predict_eval' && models[0]) {
      setParams((p) => ({ ...defaultParamsFromSchema(sch), model_id: models[0].id }));
    }
  };

  const toggleBlock = (key) => {
    const opt = BLOCK_OPTIONS.find((o) => o.key === key);
    const next = { ...blocks, [key]: !blocks[key] };
    if (!next[key]) {
      if (key === 'query') {
        next.predict = false;
        next.query_predict = false;
      }
      if (key === 'predict') next.query_predict = false;
      if (key === 'curation') next.human_gate = false;
    }
    if (next[key] && opt?.needs) {
      opt.needs.forEach((dep) => { next[dep] = true; });
    }
    if (next.curation && !next.query && !next.query_predict) {
      next.query = true;
    }
    setBlocks(next);
    setPreset('custom');
    setParams(defaultParamsFromSchema(paramsSchemaForBlocks(next)));
  };

  const handleLaunch = () => {
    if (blocks.predict && !params.model_id) return;
    onLaunch({
      name: name.trim() || undefined,
      definition: { params_schema: schema, steps },
      params,
    });
  };

  const canLaunch = steps.length > 0 && (!blocks.predict || params.model_id);

  return (
    <div className="wf-composer">
      <div className="wf-composer-presets">
        <span className="wf-composer-label">快速预设</span>
        <button
          type="button"
          className={`wf-preset-btn${preset === 'daily_ng_curation' ? ' is-active' : ''}`}
          onClick={() => loadPreset('daily_ng_curation')}
        >
          每日捞图出站
        </button>
        <button
          type="button"
          className={`wf-preset-btn${preset === 'weekly_predict_eval' ? ' is-active' : ''}`}
          onClick={() => loadPreset('weekly_predict_eval')}
        >
          每周预测评测
        </button>
      </div>

      <div className="wf-composer-layout">
        <aside className="wf-composer-blocks">
          <h4>流程能力块</h4>
          <p className="wf-muted">勾选后自动串联；无需写 JSON</p>
          {BLOCK_OPTIONS.map((opt) => {
            const disabled = opt.needs?.some((d) => !blocks[d] && opt.key !== 'query');
            const needsPredict = opt.key === 'curation' && !blocks.query && !blocks.query_predict;
            return (
              <label
                key={opt.key}
                className={`wf-block-card${blocks[opt.key] ? ' is-on' : ''}${needsPredict ? ' is-disabled' : ''}`}
              >
                <input
                  type="checkbox"
                  checked={Boolean(blocks[opt.key])}
                  disabled={needsPredict}
                  onChange={() => toggleBlock(opt.key)}
                />
                <div>
                  <strong>{opt.label}</strong>
                  <span>{opt.desc}</span>
                </div>
              </label>
            );
          })}
        </aside>

        <div className="wf-composer-main">
          <h4>流程预览</h4>
          <WorkflowPipelineViz steps={steps} />

          <div className="wf-composer-params">
            <h4>运行参数</h4>
            <label className="wf-param-row">
              <span>运行名称（可选）</span>
              <input
                className="form-input"
                type="text"
                placeholder="如：6月7日 NG 捞取"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
            <WorkflowParamsForm
              schema={schema}
              value={params}
              onChange={setParams}
              models={models}
            />
          </div>

          <div className="wf-composer-actions">
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy || !canLaunch}
              onClick={handleLaunch}
            >
              启动此流程
            </button>
            {!canLaunch && blocks.predict && (
              <span className="wf-composer-hint">请先选择预测模型</span>
            )}
          </div>
        </div>
      </div>

      <details className="wf-json-fallback">
        <summary>高级：查看生成的步骤定义（只读）</summary>
        <pre>{JSON.stringify({ params_schema: schema, steps }, null, 2)}</pre>
      </details>
    </div>
  );
}
