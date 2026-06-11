import { useCallback, useEffect, useMemo, useState } from 'react';
import { buildCommandsForTier, filterCommands } from '../config/commands';

/**
 * @param {{ tier: string; onNavigate: (path: string) => void; onEvent: (event: string) => void }} options
 */
export function useCommandPalette({ tier, onNavigate, onEvent }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [activeIndex, setActiveIndex] = useState(0);

  const allCommands = useMemo(() => buildCommandsForTier(tier), [tier]);
  const filtered = useMemo(
    () => filterCommands(allCommands, query),
    [allCommands, query],
  );

  const openPalette = useCallback(() => {
    setQuery('');
    setActiveIndex(0);
    setOpen(true);
  }, []);

  const closePalette = useCallback(() => {
    setOpen(false);
    setQuery('');
    setActiveIndex(0);
  }, []);

  const runCommand = useCallback((cmd) => {
    if (!cmd) return;
    closePalette();
    if (cmd.action.type === 'navigate') {
      onNavigate(cmd.action.path);
    } else if (cmd.action.type === 'event') {
      onEvent(cmd.action.event);
    }
  }, [closePalette, onNavigate, onEvent]);

  useEffect(() => {
    const onKeyDown = (e) => {
      const mod = e.metaKey || e.ctrlKey;
      if (mod && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setOpen((v) => {
          if (v) {
            setQuery('');
            setActiveIndex(0);
          }
          return !v;
        });
        return;
      }
      if (!open) return;
      if (e.key === 'Escape') {
        e.preventDefault();
        closePalette();
        return;
      }
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((i) => (filtered.length ? (i + 1) % filtered.length : 0));
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((i) => (filtered.length ? (i - 1 + filtered.length) % filtered.length : 0));
        return;
      }
      if (e.key === 'Enter') {
        e.preventDefault();
        runCommand(filtered[activeIndex]);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [open, filtered, activeIndex, closePalette, runCommand]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  return {
    open,
    query,
    setQuery,
    activeIndex,
    setActiveIndex,
    filtered,
    openPalette,
    closePalette,
    runCommand,
  };
}
