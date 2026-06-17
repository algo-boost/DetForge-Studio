import { useCallback, useEffect, useState } from 'react';
import { api, toast } from '../api/client';
import { useHumanGates } from './useHumanGates';

const POLL_MS = 8000;

/**
 * 工作台数据：待办、摘要、Flow 卡点；含 Catalog 同步与 Resume。
 */
export function useWorkbenchData({ pollInterval = POLL_MS } = {}) {
  const [todos, setTodos] = useState([]);
  const [summary, setSummary] = useState(null);
  const [busy, setBusy] = useState(false);

  const {
    items: gateItems,
    count: gateCount,
    reload: reloadGates,
  } = useHumanGates({ pollInterval, enabled: true });

  const loadMeta = useCallback(async () => {
    try {
      const [t, s] = await Promise.all([
        api.workbenchTodos(),
        api.workbenchSummary(),
      ]);
      if (t.success) setTodos(t.data || []);
      if (s.success) setSummary(s.data || null);
    } catch (e) {
      toast(String(e.message || e), 'error');
    }
  }, []);

  const load = useCallback(async () => {
    await Promise.all([loadMeta(), reloadGates()]);
  }, [loadMeta, reloadGates]);

  useEffect(() => {
    loadMeta();
  }, [loadMeta]);

  const syncCatalog = useCallback(async () => {
    setBusy(true);
    try {
      const r = await api.catalogSync();
      if (r.success) {
        toast('Catalog 已同步', 'success');
        await load();
      } else {
        toast(r.data?.error || '同步失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  }, [load]);

  const resumeFlow = useCallback(async (item) => {
    const runKey = item?.meta?.run_key
      || (item?.href?.includes('/flows/runs/') ? decodeURIComponent(item.href.split('/flows/runs/')[1] || '') : '');
    if (!runKey) return;
    setBusy(true);
    try {
      const r = await api.orchestrationResume({ run_key: runKey });
      if (r.success) {
        toast('已继续执行', 'success');
        await load();
      } else {
        toast(r.error || 'Resume 失败', 'error');
      }
    } catch (e) {
      toast(String(e.message || e), 'error');
    } finally {
      setBusy(false);
    }
  }, [load]);

  return {
    todos,
    summary,
    gateItems,
    gateCount,
    busy,
    reload: load,
    syncCatalog,
    resumeFlow,
  };
}
