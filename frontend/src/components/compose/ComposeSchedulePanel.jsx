import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, toast } from '../../api/client';
import {
  COMPOSE_CRON_PRESETS,
  cronPresetFromExpr,
  normalizeFlowId,
  reindexComposeSteps,
} from '../../lib/composeModules';

export default function ComposeSchedulePanel({
  flowId,
  name,
  steps,
  runParamsDefaults,
  validate,
  busy,
  onBusyChange,
  onScheduleChange,
  initialSchedule,
}) {
  const [schedule, setSchedule] = useState(initialSchedule || null);
  const [cronPreset, setCronPreset] = useState('daily_02');
  const [customCron, setCustomCron] = useState('0 2 * * *');
  const [enabled, setEnabled] = useState(true);

  const cronExpr = useMemo(() => {
    if (cronPreset === 'custom') return customCron.trim();
    const preset = COMPOSE_CRON_PRESETS.find((p) => p.id === cronPreset);
    return preset?.cron || customCron.trim();
  }, [cronPreset, customCron]);

  const syncFromSchedule = useCallback((sched) => {
    setSchedule(sched || null);
    if (sched?.cron_expr) {
      const presetId = cronPresetFromExpr(sched.cron_expr);
      setCronPreset(presetId);
      if (presetId === 'custom') setCustomCron(sched.cron_expr);
    }
    if (sched && sched.enabled != null) setEnabled(Boolean(sched.enabled));
    onScheduleChange?.(sched || null);
  }, [onScheduleChange]);

  useEffect(() => {
    syncFromSchedule(initialSchedule || null);
  }, [initialSchedule, syncFromSchedule]);

  const loadSchedule = useCallback(async (id) => {
    const fid = normalizeFlowId(id);
    if (!fid || fid === 'flow_draft') {
      syncFromSchedule(null);
      return;
    }
    try {
      const r = await api.forgeComposeFlowScheduleGet(fid);
      if (r.success) syncFromSchedule(r.data || null);
    } catch {
      syncFromSchedule(null);
    }
  }, [syncFromSchedule]);

  useEffect(() => {
    loadSchedule(flowId);
  }, [flowId, loadSchedule]);

  const saveSchedule = async () => {
    const fid = normalizeFlowId(flowId);
    if (!fid || fid === 'flow_draft') {
      toast('请先保存流水线（非 flow_draft）再配置定时', 'error');
      return;
    }
    if (validate && !validate()) return;
    if (!cronExpr) {
      toast('请填写 cron 表达式', 'error');
      return;
    }
    onBusyChange?.(true);
    try {
      const indexed = reindexComposeSteps(fid, steps);
      const r = await api.forgeComposeFlowScheduleSave(fid, {
        flow_id: fid,
        name: name?.trim() || fid,
        step_instances: indexed,
        run_params_defaults: runParamsDefaults,
        ...runParamsDefaults,
        cron_expr: cronExpr,
        enabled: enabled ? 1 : 0,
      });
      if (r.success) {
        syncFromSchedule(r.data);
        toast('定时调度已保存', 'success');
      }
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      onBusyChange?.(false);
    }
  };

  const toggleEnabled = async () => {
    if (!schedule?.id) {
      setEnabled((v) => !v);
      return;
    }
    onBusyChange?.(true);
    try {
      await api.forgeWorkflowScheduleUpdate(schedule.id, { enabled: schedule.enabled ? 0 : 1 });
      await loadSchedule(flowId);
      toast(schedule.enabled ? '定时已停用' : '定时已启用', 'success');
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      onBusyChange?.(false);
    }
  };

  const triggerNow = async () => {
    if (!schedule?.id) {
      toast('请先保存定时调度', 'error');
      return;
    }
    onBusyChange?.(true);
    try {
      const r = await api.forgeWorkflowScheduleTrigger(schedule.id);
      if (r.success) {
        toast(r.skipped ? '已跳过（互斥或上次未完成）' : `已触发运行 #${r.data?.id}`, r.skipped ? 'info' : 'success');
        await loadSchedule(flowId);
      }
    } catch (e) {
      toast(e.message || String(e), 'error');
    } finally {
      onBusyChange?.(false);
    }
  };

  const isDraft = !flowId || normalizeFlowId(flowId) === 'flow_draft';

  return (
    <section className="compose-schedule-panel platform-surface-card">
      <div className="compose-schedule-header">
        <div>
          <h3 className="compose-schedule-title">定时调度</h3>
          <p className="muted compose-schedule-hint">
            保存流水线后可按 cron 自动运行，参数与上方「运行参数」一致。
          </p>
        </div>
        <div className="compose-schedule-actions">
          <label className="compose-schedule-toggle">
            <input
              type="checkbox"
              checked={schedule?.id ? Boolean(schedule.enabled) : enabled}
              disabled={busy || isDraft}
              onChange={toggleEnabled}
            />
            <span>{(schedule?.id ? schedule.enabled : enabled) ? '已启用' : '已停用'}</span>
          </label>
          <button type="button" className="btn btn-secondary btn-sm" disabled={busy || isDraft} onClick={saveSchedule}>
            保存调度
          </button>
          <button
            type="button"
            className="btn btn-sm"
            disabled={busy || !schedule?.id}
            onClick={triggerNow}
          >
            立即触发
          </button>
        </div>
      </div>

      <div className="compose-schedule-fields">
        <label className="compose-schedule-field">
          <span>执行频率</span>
          <select
            className="form-select"
            value={cronPreset}
            disabled={busy || isDraft}
            onChange={(e) => setCronPreset(e.target.value)}
          >
            {COMPOSE_CRON_PRESETS.map((p) => (
              <option key={p.id} value={p.id}>{p.label}</option>
            ))}
          </select>
        </label>
        {cronPreset === 'custom' && (
          <label className="compose-schedule-field compose-schedule-cron-custom">
            <span>Cron（分 时 日 月 周）</span>
            <input
              className="form-input"
              type="text"
              spellCheck={false}
              placeholder="0 2 * * *"
              value={customCron}
              disabled={busy || isDraft}
              onChange={(e) => setCustomCron(e.target.value)}
            />
          </label>
        )}
        <div className="compose-schedule-meta">
          <span>
            表达式：<code>{cronExpr || '—'}</code>
          </span>
          {schedule?.next_run_at && (
            <span>下次运行：{schedule.next_run_at}</span>
          )}
          {schedule?.last_triggered_at && (
            <span>上次触发：{schedule.last_triggered_at}</span>
          )}
        </div>
      </div>

      {isDraft && (
        <p className="muted compose-schedule-draft-note">保存流水线后可配置定时任务。</p>
      )}
    </section>
  );
}
