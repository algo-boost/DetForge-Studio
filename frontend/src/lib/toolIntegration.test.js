import { describe, expect, it } from 'vitest';
import { normalizeToolIntegration, buildToolIframeSrc } from './toolIntegration';
import { getToolIntegrationSpec } from '../config/toolIntegration';

describe('normalizeToolIntegration', () => {
  it('defaults to embedded', () => {
    const spec = getToolIntegrationSpec('query');
    const out = normalizeToolIntegration({}, spec);
    expect(out.integration).toBe('embedded');
    expect(out.mountPrefix).toBe('/tools/query');
  });

  it('parses remote_url', () => {
    const spec = getToolIntegrationSpec('query');
    const out = normalizeToolIntegration(
      { integration: 'remote', remote_url: 'http://localhost:6021/', mount_prefix: '/tools/query' },
      spec,
    );
    expect(out.integration).toBe('remote');
    expect(out.remoteUrl).toBe('http://localhost:6021');
  });
});

describe('buildToolIframeSrc', () => {
  it('builds hash route for query', () => {
    expect(buildToolIframeSrc({
      base: '/tools/query',
      routing: 'hash',
      segment: 'query-results',
      search: '?task=abc',
      hashRouting: true,
    })).toBe('/tools/query#/query-results?task=abc');
  });

  it('builds path route for viz', () => {
    expect(buildToolIframeSrc({
      base: '/viz',
      routing: 'path',
      segment: '',
      search: '?session=x',
      hashRouting: false,
    })).toBe('/viz/?session=x');
  });
});
