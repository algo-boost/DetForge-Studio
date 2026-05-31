import { useCallback, useEffect, useRef, useState } from 'react';

const DEFAULT_HEIGHT = 320;
const DEFAULT_SQL_PCT = 100 / 3;

function clampHeight(h) {
  return Math.max(160, Math.min(window.innerHeight * 0.75, h));
}

function clampSqlPct(pct) {
  return Math.max(20, Math.min(70, pct));
}

export function useEditorWorkspace() {
  const workspaceRef = useRef(null);
  const splitRef = useRef(null);
  const sqlPaneRef = useRef(null);

  const [height, setHeight] = useState(() => {
    const saved = parseInt(localStorage.getItem('pc_editor_height') || '', 10);
    return Number.isFinite(saved) ? clampHeight(saved) : DEFAULT_HEIGHT;
  });
  const [sqlPct, setSqlPct] = useState(() => {
    const saved = parseFloat(localStorage.getItem('pc_editor_sql_pct') || '');
    return Number.isFinite(saved) ? clampSqlPct(saved) : DEFAULT_SQL_PCT;
  });
  const [fullscreenPane, setFullscreenPane] = useState(null);

  const applyHeight = useCallback((h) => {
    const next = clampHeight(h);
    setHeight(next);
    localStorage.setItem('pc_editor_height', String(next));
  }, []);

  const applySqlPct = useCallback((pct) => {
    const next = clampSqlPct(pct);
    setSqlPct(next);
    localStorage.setItem('pc_editor_sql_pct', String(next));
  }, []);

  const toggleFullscreen = useCallback((pane) => {
    setFullscreenPane((cur) => (cur === pane ? null : pane));
  }, []);

  useEffect(() => {
    if (!fullscreenPane) return undefined;
    const onKey = (e) => {
      if (e.key === 'Escape') setFullscreenPane(null);
    };
    window.addEventListener('keydown', onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [fullscreenPane]);

  useEffect(() => {
    const handle = document.getElementById('editor-col-resize-handle');
    const split = splitRef.current;
    const sqlPane = sqlPaneRef.current;
    if (!handle || !split || !sqlPane) return undefined;

    let startX = 0;
    let startW = 0;

    const onMove = (e) => {
      if (fullscreenPane) return;
      const clientX = e.touches ? e.touches[0].clientX : e.clientX;
      const splitW = split.getBoundingClientRect().width;
      if (splitW <= 0) return;
      applySqlPct(((startW + (clientX - startX)) / splitW) * 100);
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    const onStart = (e) => {
      if (fullscreenPane) return;
      e.preventDefault();
      startX = e.touches ? e.touches[0].clientX : e.clientX;
      startW = sqlPane.getBoundingClientRect().width;
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onUp);
    };

    handle.addEventListener('mousedown', onStart);
    handle.addEventListener('touchstart', onStart, { passive: false });
    return () => {
      handle.removeEventListener('mousedown', onStart);
      handle.removeEventListener('touchstart', onStart);
      onUp();
    };
  }, [fullscreenPane, applySqlPct]);

  useEffect(() => {
    const handle = document.getElementById('editor-resize-handle');
    const workspace = workspaceRef.current;
    if (!handle || !workspace) return undefined;

    let startY = 0;
    let startH = 0;

    const onMove = (e) => {
      if (fullscreenPane) return;
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      applyHeight(startH + (clientY - startY));
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      document.removeEventListener('touchmove', onMove);
      document.removeEventListener('touchend', onUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };

    const onStart = (e) => {
      if (fullscreenPane) return;
      e.preventDefault();
      startY = e.touches ? e.touches[0].clientY : e.clientY;
      startH = workspace.getBoundingClientRect().height;
      document.body.style.cursor = 'ns-resize';
      document.body.style.userSelect = 'none';
      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
      document.addEventListener('touchmove', onMove, { passive: false });
      document.addEventListener('touchend', onUp);
    };

    handle.addEventListener('mousedown', onStart);
    handle.addEventListener('touchstart', onStart, { passive: false });
    return () => {
      handle.removeEventListener('mousedown', onStart);
      handle.removeEventListener('touchstart', onStart);
      onUp();
    };
  }, [fullscreenPane, applyHeight]);

  return {
    workspaceRef,
    splitRef,
    sqlPaneRef,
    height,
    sqlPct,
    fullscreenPane,
    toggleFullscreen,
  };
}

export function FullscreenIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
    </svg>
  );
}
