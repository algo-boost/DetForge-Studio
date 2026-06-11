import { useEffect, useRef } from 'react';

/**
 * 统一轮询：标签页隐藏时自动暂停、可见时恢复并立即拉取一次；enabled=false 时停止；卸载时清理。
 *
 * callback 用 ref 持有最新引用，因此定时器不会因 callback 每次渲染重建而被反复销毁重建，
 * 只有 interval / enabled / immediate 变化时才会重置 —— 避免节奏漂移与请求叠加。
 *
 * @param {() => void | Promise<void>} callback 每个 tick 执行的拉取逻辑
 * @param {{ interval?: number, enabled?: boolean, immediate?: boolean }} [options]
 *   interval: 轮询间隔（ms，默认 8000）；enabled: 是否启用（默认 true）；
 *   immediate: 启用时是否立即执行一次（默认 true）
 */
export function usePolling(callback, { interval = 8000, enabled = true, immediate = true } = {}) {
  const savedCallback = useRef(callback);
  savedCallback.current = callback;

  useEffect(() => {
    if (!enabled) return undefined;

    const tick = () => savedCallback.current?.();
    let timer = null;
    const start = () => {
      if (timer == null) timer = setInterval(tick, interval);
    };
    const stop = () => {
      if (timer != null) {
        clearInterval(timer);
        timer = null;
      }
    };
    const onVisibility = () => {
      if (typeof document !== 'undefined' && document.hidden) {
        stop();
      } else {
        tick();
        start();
      }
    };

    const hidden = typeof document !== 'undefined' && document.hidden;
    if (immediate && !hidden) tick();
    if (!hidden) start();

    if (typeof document !== 'undefined') {
      document.addEventListener('visibilitychange', onVisibility);
    }
    return () => {
      stop();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility);
      }
    };
  }, [interval, enabled, immediate]);
}
