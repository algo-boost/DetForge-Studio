import { useEffect, useState } from 'react';
import { getToolIntegrationSpec } from '../config/toolIntegration';
import { loadToolIntegration, resetToolIntegrationCache } from '../lib/toolIntegration';

const DEFAULT_STATE = {
  loading: true,
  integration: 'embedded',
  remoteUrl: '',
  standaloneUrl: '',
  mountPrefix: '',
  hashRouting: false,
  available: true,
  mounted: false,
  built: true,
};

/**
 * 读取工具集成模式（embedded / remote / standalone）。
 * @param {string} toolId — query | viz | unify
 */
export function useToolIntegration(toolId) {
  const spec = getToolIntegrationSpec(toolId);
  const [state, setState] = useState({
    ...DEFAULT_STATE,
    mountPrefix: spec.defaultMount,
    hashRouting: spec.routing === 'hash',
  });

  useEffect(() => {
    let cancelled = false;
    setState((s) => ({ ...s, loading: true }));
    loadToolIntegration(toolId)
      .then((data) => {
        if (cancelled) return;
        setState({ ...data, loading: false });
      })
      .catch(() => {
        if (cancelled) return;
        setState({
          ...DEFAULT_STATE,
          loading: false,
          mountPrefix: spec.defaultMount,
          hashRouting: spec.routing === 'hash',
        });
      });
    return () => { cancelled = true; };
  }, [toolId, spec.defaultMount, spec.routing]);

  return state;
}

/** @deprecated 使用 useToolIntegration('query') */
export function useQueryIntegration() {
  return useToolIntegration('query');
}

export function resetQueryIntegrationCache() {
  resetToolIntegrationCache('query');
}

export { resetToolIntegrationCache };
