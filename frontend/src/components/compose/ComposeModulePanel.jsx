import { useState } from 'react';
import { ComposeModuleBody } from './composeModuleRegistry';
import ComposeUpstreamBanner from './ComposeUpstreamBanner';
import { stepMeta } from '../../lib/workflowCatalog';

/**
 * 组合编排模块面板：单步配置 + 排序/删除 + 上游接入说明。
 */
export default function ComposeModulePanel({
  step,
  stepIndex,
  totalSteps,
  moduleId,
  paramsSchema,
  bindHints = [],
  value,
  onChange,
  onMoveUp,
  onMoveDown,
  onRemove,
  models = [],
  canRemove = true,
  defaultCollapsed = false,
  /** 受控展开（手风琴） */
  expanded,
  onExpand,
}) {
  const mod = step;
  const meta = stepMeta(mod.kind);
  const [internalCollapsed, setInternalCollapsed] = useState(defaultCollapsed);
  const isControlled = expanded !== undefined;
  const collapsed = isControlled ? !expanded : internalCollapsed;

  const toggleCollapsed = () => {
    if (isControlled) {
      if (collapsed) onExpand?.(step.uid);
      else onExpand?.(null);
      return;
    }
    setInternalCollapsed((c) => !c);
  };

  const hasBind = bindHints.length > 0;

  return (
    <section
      className={`compose-step-panel platform-surface-card${collapsed ? ' is-collapsed' : ''}`}
      aria-labelledby={`compose-step-${step.uid}`}
    >
      <header
        className="compose-step-header compose-step-header--interactive"
        onClick={collapsed ? toggleCollapsed : undefined}
        onKeyDown={collapsed ? (e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggleCollapsed();
          }
        } : undefined}
        role={collapsed ? 'button' : undefined}
        tabIndex={collapsed ? 0 : undefined}
      >
        <span className="compose-step-badge" style={{ '--wf-node-color': meta.color }}>
          {stepIndex + 1}
        </span>
        <div className="compose-step-header-main">
          <h3 id={`compose-step-${step.uid}`} className="compose-step-title">
            {mod.label}
          </h3>
          {meta.desc && <p className="compose-step-desc muted">{meta.desc}</p>}
        </div>
        <div className="compose-step-actions" onClick={(e) => e.stopPropagation()} onKeyDown={(e) => e.stopPropagation()}>
          <button
            type="button"
            className="btn btn-sm btn-ghost"
            onClick={toggleCollapsed}
            aria-expanded={!collapsed}
          >
            {collapsed ? '展开' : '收起'}
          </button>
          <button type="button" className="btn btn-sm" disabled={stepIndex === 0} onClick={onMoveUp} title="上移">↑</button>
          <button type="button" className="btn btn-sm" disabled={stepIndex >= totalSteps - 1} onClick={onMoveDown} title="下移">↓</button>
          {canRemove && totalSteps > 1 && (
            <button type="button" className="btn btn-sm" onClick={onRemove} title="移除">移除</button>
          )}
        </div>
      </header>

      {hasBind && <ComposeUpstreamBanner bindHints={bindHints} />}

      {!collapsed && (
        <ComposeModuleBody
          moduleId={moduleId}
          paramsSchema={paramsSchema}
          value={value}
          onChange={onChange}
          bindHints={bindHints}
          models={models}
        />
      )}
      {collapsed && (
        <p className="compose-step-collapsed-hint muted">已收起 · 点击「展开」编辑此步骤</p>
      )}
    </section>
  );
}
