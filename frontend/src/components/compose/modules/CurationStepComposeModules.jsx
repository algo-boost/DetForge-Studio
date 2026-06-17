import WorkflowParamsForm from '../../forge/WorkflowParamsForm';

function StepCard({ num, title, desc, children }) {
  return (
    <section className="platform-step platform-surface-card">
      <div className="platform-step-head">
        <span className="platform-step-num">{num}</span>
        <div>
          <h4>{title}</h4>
          {desc && <p className="muted">{desc}</p>}
        </div>
      </div>
      {children}
    </section>
  );
}

/** 导出 COCO 出站包 */
export function CurationExportComposeModule({ value, onChange, bindHints = [] }) {
  const batchBound = bindHints.some((h) => h.param === 'batch_id' && h.ok);
  return (
    <div className="compose-module-curation-step">
      {batchBound && <p className="compose-step-hint is-ok">batch_id 将自动绑定上游「创建筛选批次」</p>}
      <StepCard num="1" title="出站选项" desc="生成 Label Studio / CVAT 可导入的 COCO 包">
        <label className="wf-param-row compose-check-row">
          <input
            type="checkbox"
            checked={value?.include_images !== false}
            onChange={(e) => onChange({ ...value, include_images: e.target.checked })}
          />
          <span>包含图片文件（体积较大；仅 JSON 时可取消）</span>
        </label>
      </StepCard>
    </div>
  );
}

/** 人工卡点 */
export function GateHumanComposeModule({ value, onChange, bindHints = [] }) {
  const batchBound = bindHints.some((h) => h.param === 'batch_id' && h.ok);
  return (
    <div className="compose-module-curation-step">
      {batchBound && <p className="compose-step-hint is-ok">batch_id 将自动绑定上游批次</p>}
      <StepCard num="1" title="卡点类型" desc="流程在此暂停，等待人工完成标注后自动继续">
        <div className="forge-form-grid platform-predict-form">
          <label className="forge-span2">
            卡点类型
            <select
              value={value?.gate_type || 'curation_coco_edit'}
              onChange={(e) => onChange({ ...value, gate_type: e.target.value })}
            >
              <option value="curation_coco_edit">COCO 编辑（出站 → 人工 → 回传）</option>
            </select>
          </label>
          <label className="forge-span2">
            操作说明
            <textarea
              rows={3}
              value={value?.instructions || ''}
              onChange={(e) => onChange({ ...value, instructions: e.target.value })}
              placeholder="请编辑出站 COCO 并上传后继续"
            />
          </label>
        </div>
      </StepCard>
    </div>
  );
}

/** 导入 COCO 回传 */
export function CurationImportComposeModule({ bindHints = [] }) {
  const batchBound = bindHints.some((h) => h.param === 'batch_id' && h.ok);
  return (
    <div className="compose-module-curation-step">
      {batchBound && <p className="compose-step-hint is-ok">batch_id 将自动绑定上游批次</p>}
      <StepCard num="1" title="COCO 回传" desc="运行时将匹配人工编辑后的 COCO 并更新留/剔标记">
        <p className="muted">此步骤无需额外参数；请确保上游已导出并在人工平台完成标注。</p>
      </StepCard>
    </div>
  );
}

/** 筛选归档 */
export function CurationArchiveComposeModule({ value, onChange, bindHints = [] }) {
  const batchBound = bindHints.some((h) => h.param === 'batch_id' && h.ok);
  return (
    <div className="compose-module-curation-step">
      {batchBound && <p className="compose-step-hint is-ok">batch_id 将自动绑定上游批次</p>}
      <StepCard num="1" title="归档选项" desc="将保留样本复制到归档目录并生成交接包">
        <label className="wf-param-row compose-check-row">
          <input
            type="checkbox"
            checked={value?.copy_images !== false}
            onChange={(e) => onChange({ ...value, copy_images: e.target.checked })}
          />
          <span>复制图片到归档目录</span>
        </label>
      </StepCard>
    </div>
  );
}

/** 流程通知 */
export function NotifyComposeModule({ value, onChange }) {
  return (
    <div className="compose-module-notify">
      <StepCard num="1" title="通知事件" desc="流程结束时触发的事件标识（可对接 webhook / 消息）">
        <div className="forge-form-grid platform-predict-form">
          <label className="forge-span2">
            事件名
            <input
              type="text"
              value={value?.event || 'workflow_done'}
              onChange={(e) => onChange({ ...value, event: e.target.value })}
            />
          </label>
        </div>
      </StepCard>
    </div>
  );
}

/** 无专用完整 UI 时的兜底（保留 schema 表单） */
export function SchemaFallbackModule({ paramsSchema, value, onChange, models }) {
  return (
    <WorkflowParamsForm
      schema={paramsSchema}
      value={value}
      onChange={onChange}
      models={models}
    />
  );
}
