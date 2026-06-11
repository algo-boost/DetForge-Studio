/** 供非 React 模块（如 api/client）触发 SPA 内跳转 */
let navigateFn = null;

export function setAppNavigate(fn) {
  navigateFn = fn;
}

export function appNavigate(to) {
  if (navigateFn) {
    navigateFn(to);
    return true;
  }
  return false;
}
