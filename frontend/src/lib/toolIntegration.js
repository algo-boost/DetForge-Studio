import { getToolIntegrationSpec } from '../config/toolIntegration';

const cache = new Map();
const inflight = new Map();

/** @typedef {'embedded'|'remote'|'standalone'} IntegrationMode */

/**
 * @returns {{
 *   integration: IntegrationMode,
 *   remoteUrl: string,
 *   standaloneUrl: string,
 *   mountPrefix: string,
 *   hashRouting: boolean,
 *   available: boolean,
 *   mounted: boolean,
 *   built: boolean,
 *   raw: object,
 * }}
 */
export function normalizeToolIntegration(json, spec) {
  const integration = json?.integration || 'embedded';
  const remoteUrl = String(json?.remote_url || '').replace(/\/$/, '');
  const standaloneUrl = String(json?.standalone_url || '').replace(/\/$/, '');
  const mountPrefix = json?.mount_prefix || spec.defaultMount || '';
  return {
    integration,
    remoteUrl,
    standaloneUrl,
    mountPrefix,
    hashRouting: json?.hash_routing ?? spec.routing === 'hash',
    available: json?.available ?? json?.mount_available ?? true,
    mounted: json?.mounted ?? json?.mount_ready ?? false,
    built: json?.built ?? true,
    raw: json || {},
  };
}

async function fetchStatus(url) {
  const res = await fetch(url, { credentials: 'same-origin' });
  if (!res.ok) return null;
  return res.json();
}

/**
 * 拉取工具集成配置（带 per-tool 缓存）。
 * @param {string} toolId
 */
export async function loadToolIntegration(toolId) {
  if (cache.has(toolId)) {
    return cache.get(toolId);
  }
  if (inflight.has(toolId)) {
    return inflight.get(toolId);
  }

  const spec = getToolIntegrationSpec(toolId);
  const promise = (async () => {
    let json = await fetchStatus(spec.statusPath);
    if (!json && spec.legacyStatusPath) {
      json = await fetchStatus(spec.legacyStatusPath);
    }
    const normalized = normalizeToolIntegration(json || {}, spec);
    cache.set(toolId, normalized);
    return normalized;
  })().finally(() => {
    inflight.delete(toolId);
  });

  inflight.set(toolId, promise);
  return promise;
}

export function resetToolIntegrationCache(toolId) {
  if (toolId) cache.delete(toolId);
  else cache.clear();
}

/**
 * 构建 iframe src。
 * @param {{ base: string, routing: 'hash'|'path', segment: string, search: string, hashRouting?: boolean }} opts
 */
export function buildToolIframeSrc({ base, routing, segment, search, hashRouting }) {
  const root = String(base || '').replace(/\/$/, '');
  const qs = search || '';
  const useHash = hashRouting ?? routing === 'hash';
  if (useHash) {
    const seg = segment ? `/${String(segment).replace(/^\//, '')}` : '';
    return `${root}#${seg || '/'}${qs}`;
  }
  const path = segment ? `/${String(segment).replace(/^\//, '')}` : '';
  return `${root}${path || '/'}${qs}`;
}
