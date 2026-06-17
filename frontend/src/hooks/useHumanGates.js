import { useCallback, useEffect, useMemo, useState } from 'react';
import { api, toast } from '../api/client';
import { usePolling } from './usePolling';

export const HUMAN_GATE_STATUS = 'waiting_human';
const DEFAULT_POLL_MS = 8000;

/** @param {Array<{ status?: string }>} runs */
export function filterWaitingHumanRuns(runs = []) {
  return runs.filter((r) => r.status === HUMAN_GATE_STATUS);
}

/** @param {{ steps?: Array<{ status?: string }> } | null | undefined} runDetail */
export function findGateStep(runDetail) {
  return runDetail?.steps?.find((s) => s.status === HUMAN_GATE_STATUS) ?? null;
}

/** @param {{ child_batch_id?: string, human_action?: { batch_id?: string } } | null} gateStep */
export function getGateBatchId(gateStep) {
  if (!gateStep) return null;
  return gateStep.child_batch_id || gateStep.human_action?.batch_id || null;
}

/** @param {Record<string, unknown>} run */
export function workflowRunToGateItem(run) {
  const runId = run.id;
  const templateId = run.template_id || run.name || '工作流';
  return {
    id: `workflow-${runId}`,
    kind: 'workflow_human_gate',
    title: `${templateId} · 待人工处理`,
    subtitle: `Run #${runId}`,
    status: HUMAN_GATE_STATUS,
    href: `/flows/runs/workflow:${runId}`,
    created_at: run.created_at || run.started_at,
    meta: { run_id: runId, template_id: run.template_id, run_key: `workflow:${runId}` },
  };
}

/** @param {Record<string, unknown>} flow */
export function flowRunToGateItem(flow) {
  if (flow.source === 'workflow') {
    const runId = flow.run_id;
    return {
      id: `workflow-${runId}`,
      kind: 'workflow_human_gate',
      title: `${flow.flow_id || '工作流'} · 待人工处理`,
      subtitle: `Run #${runId}`,
      status: HUMAN_GATE_STATUS,
      href: `/flows/runs/workflow:${runId}`,
      meta: { run_id: runId, run_key: `workflow:${runId}`, flow_id: flow.flow_id },
    };
  }
  return {
    id: `demo-flow-${flow.run_id}`,
    kind: 'flow_human_gate',
    title: `${flow.flow_id || flow.run_id} · 演示 Flow`,
    subtitle: flow.pause_at ? `暂停于 ${flow.pause_at}` : String(flow.run_id),
    status: HUMAN_GATE_STATUS,
    href: `/flows/runs/demo:${encodeURIComponent(flow.run_id)}`,
    meta: { run_id: flow.run_id, flow_id: flow.flow_id, pause_at: flow.pause_at, run_key: `demo:${flow.run_id}` },
  };
}

/**
 * 聚合 workflow / demo 人工卡点，供 Home、Flows、Workflows 共用。
 * @param {{ pollInterval?: number | false, enabled?: boolean }} [options]
 */
export function useHumanGates({ pollInterval = DEFAULT_POLL_MS, enabled = true } = {}) {
  const [workflowGates, setWorkflowGates] = useState([]);
  const [flowGates, setFlowGates] = useState([]);

  const load = useCallback(async () => {
    try {
      const [w, f] = await Promise.all([
        api.forgeWorkflowRuns(`?status=${HUMAN_GATE_STATUS}&limit=50`),
        api.workbenchFlowRuns(`?status=${HUMAN_GATE_STATUS}&limit=20`),
      ]);
      if (w.success) {
        const rows = w.data || [];
        setWorkflowGates(filterWaitingHumanRuns(rows));
      }
      if (f.success) setFlowGates(f.data || []);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  useEffect(() => {
    if (enabled) load();
  }, [enabled, load]);

  usePolling(load, {
    interval: typeof pollInterval === 'number' ? pollInterval : DEFAULT_POLL_MS,
    immediate: false,
    enabled: enabled && pollInterval !== false,
  });

  const items = useMemo(
    () => [
      ...workflowGates.map(workflowRunToGateItem),
      ...flowGates.map(flowRunToGateItem),
    ],
    [workflowGates, flowGates],
  );

  return {
    workflowGates,
    flowGates,
    items,
    count: items.length,
    reload: load,
    filterWaitingHumanRuns,
    findGateStep,
    getGateBatchId,
  };
}
