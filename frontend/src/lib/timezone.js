/** 应用时区：配置页写入，文档/列表展示读取 */

let appTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai';

export const TIMEZONE_OPTIONS = [
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'UTC',
  'America/New_York',
  'Europe/London',
];

export function timezoneLabel(tz) {
  const v = String(tz || appTimezone || 'Asia/Shanghai').trim();
  try {
    const parts = new Intl.DateTimeFormat('zh-CN', {
      timeZone: v,
      timeZoneName: 'longOffset',
    }).formatToParts(new Date());
    const offset = parts.find((p) => p.type === 'timeZoneName')?.value || '';
    return offset ? `${v} (${offset})` : v;
  } catch {
    return v;
  }
}

export function setAppTimezone(tz) {
  const v = String(tz || '').trim();
  if (v) appTimezone = v;
}

export function getAppTimezone() {
  return appTimezone;
}

/** 按应用时区取年月日时分（manual-qc 批次 ID 等） */
export function zonedParts(date = new Date(), tz = appTimezone) {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone: tz,
    year: 'numeric',
    month: 'numeric',
    day: 'numeric',
    hour: 'numeric',
    minute: 'numeric',
    second: 'numeric',
    hour12: false,
  }).formatToParts(date);
  const get = (type) => Number(parts.find((p) => p.type === type)?.value || 0);
  return {
    year: get('year'),
    month: get('month'),
    day: get('day'),
    hour: get('hour'),
    minute: get('minute'),
    second: get('second'),
  };
}

export function formatDisplayTime(isoOrTs, options = {}) {
  if (isoOrTs == null || isoOrTs === '') return '—';
  try {
    const d = new Date(isoOrTs);
    if (Number.isNaN(d.getTime())) return String(isoOrTs);
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: appTimezone,
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      ...options,
    }).format(d);
  } catch {
    return String(isoOrTs);
  }
}
