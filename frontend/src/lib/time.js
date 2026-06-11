/** 秒 → 人类可读时长（350ms / 2.1s / 1m5s）。compact=false 时用「分/秒」。 */
export function formatDuration(sec, { compact = true } = {}) {
  if (sec == null || Number.isNaN(sec)) return null;
  if (sec < 1) return `${Math.round(sec * 1000)}ms`;
  if (sec < 60) return `${sec.toFixed(1)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return compact ? `${m}m${s}s` : `${m} 分 ${s} 秒`;
}

/** ISO 字符串 → 本地时间展示，解析失败时回退原值。 */
export function formatDateTime(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleString('zh-CN', { hour12: false });
  } catch {
    return String(iso);
  }
}

export function toLocalInput(d) {
  const pad = (n) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local → SQL 环境变量格式 YYYY-MM-DD HH:mm:ss */
export function formatEnvDateTime(localInput) {
  if (localInput == null || String(localInput).trim() === '') return '';
  const s = String(localInput).trim();
  if (s.includes('T')) {
    const [date, time] = s.split('T');
    const [hh = '00', mm = '00'] = (time || '').split(':');
    return `${date} ${hh.padStart(2, '0')}:${mm.padStart(2, '0')}:00`;
  }
  return s;
}

export function setTimePreset(preset) {
  const now = new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), 0, 0);
  const endHour = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate(), d.getHours(), 59);
  let start;
  let end;
  if (preset === 'today') {
    start = startOfDay(now); end = endHour(now);
  } else if (preset === 'yesterday') {
    const y = new Date(now); y.setDate(y.getDate() - 1);
    start = startOfDay(y); end = new Date(y.getFullYear(), y.getMonth(), y.getDate(), 23, 59);
  } else if (preset === '7days') {
    start = new Date(now.getTime() - 6 * 86400000); start.setHours(0, 0, 0, 0); end = endHour(now);
  } else {
    start = new Date(now.getTime() - 29 * 86400000); start.setHours(0, 0, 0, 0); end = endHour(now);
  }
  return { start: toLocalInput(start), end: toLocalInput(end) };
}
