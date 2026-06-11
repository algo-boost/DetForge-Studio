import { describe, expect, it } from 'vitest';
import { resolveVizIframeSrc, resolveVizIframeSrcWhilePreparing } from './vizIframe';

describe('resolveVizIframeSrc', () => {
  it('defaults to /viz/', () => {
    expect(resolveVizIframeSrc({ base: '/viz' })).toBe('/viz/');
  });

  it('adds defectloop_session', () => {
    expect(resolveVizIframeSrc({ base: '/viz', session: 'abc123' }))
      .toBe('/viz/?defectloop_session=abc123');
  });

  it('uses decoded src param', () => {
    const src = encodeURIComponent('/viz/?dataset=foo');
    expect(resolveVizIframeSrc({ base: '/viz', srcParam: src })).toBe('/viz/?dataset=foo');
  });

  it('uses remote base', () => {
    expect(resolveVizIframeSrc({ base: 'http://127.0.0.1:6010', session: 'x' }))
      .toBe('http://127.0.0.1:6010/?defectloop_session=x');
  });
});

describe('resolveVizIframeSrcWhilePreparing', () => {
  it('shows placeholder while preparing', () => {
    expect(resolveVizIframeSrcWhilePreparing({
      base: '/viz',
      preparing: true,
      srcParam: null,
      session: null,
    })).toBe('/viz/');
  });

  it('ignores preparing when session present', () => {
    expect(resolveVizIframeSrcWhilePreparing({
      base: '/viz',
      preparing: true,
      session: 's1',
    })).toBe('/viz/?defectloop_session=s1');
  });
});
