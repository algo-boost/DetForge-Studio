import { useCallback, useEffect, useRef, useState } from 'react';
import { DEFAULT_RESULTS_HEIGHT } from '../lib/constants';

function clampHeight(h) {
  return Math.max(120, Math.min(window.innerHeight * 0.88, h));
}

export function useResultsResize(enabled, collapsed, fullscreen) {
  const sectionRef = useRef(null);
  const [height, setHeight] = useState(() => {
    const saved = parseInt(localStorage.getItem('pc_results_height') || '', 10);
    return Number.isFinite(saved) ? clampHeight(saved) : DEFAULT_RESULTS_HEIGHT;
  });

  const applyHeight = useCallback((h) => {
    const next = clampHeight(h);
    setHeight(next);
    localStorage.setItem('pc_results_height', String(next));
  }, []);

  useEffect(() => {
    if (!enabled || collapsed || fullscreen) return undefined;
    const handle = sectionRef.current?.querySelector('.results-resize-handle');
    const section = sectionRef.current;
    if (!handle || !section) return undefined;

    let startY = 0;
    let startH = 0;

    const onMove = (e) => {
      const clientY = e.touches ? e.touches[0].clientY : e.clientY;
      applyHeight(startH - (clientY - startY));
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
      e.preventDefault();
      startY = e.touches ? e.touches[0].clientY : e.clientY;
      startH = section.getBoundingClientRect().height;
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
  }, [enabled, collapsed, fullscreen, applyHeight]);

  return { sectionRef, height };
}
